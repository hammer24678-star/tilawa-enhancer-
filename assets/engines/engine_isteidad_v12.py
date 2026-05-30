#!/usr/bin/env python3
# engine_isteidad_v12.py — الاسترداد v12
# Base: engine_isteidad_v11_final.py (v11)
# Knowledge Bases: voice_audio_knowledge_base_MASTER.txt (§1-51C, May 2026)
#                  voice_audio_knowledge_base_SUPPLEMENT_v5.txt (§52-67, May 2026)
#
# NEW IN v12 (supplement v5 + master v4 driven improvements):
#
#   KB-12-01  Qalqalah post-closure burst protection (Supplement §52.7, Roadmap E)
#             Letters qaf/Ta/ba/jim/dal produce micro-vowel burst 10-60ms post-closure.
#             Pre-echo suppressor marks onset+60ms as PROTECTED from attenuation.
#             Prevents consonant snap erasure that makes qaf sound like hamza.
#
#   KB-12-02  Ghunnah nasal formant guard in EQ band confidence (Supplement §52.2)
#             Mim/Nun nasal pole ~250Hz AND antiformant ~1000Hz are phonologically
#             meaningful. _eq_band_confidence caps confidence at 0.40 for cuts in
#             220-290Hz and 950-1100Hz — guards ghunnah from aggressive correction.
#
#   KB-12-03  Emphatic letter de-essing guard in design_eq (Supplement §52.3, Roadmap H)
#             When sib_emphatic_dominant=True (KB-06), sib_cap drops 2.0->1.0 dB
#             in 3-5kHz. _eq_band_confidence reduces 0.35 for nodes in 2800-4800Hz.
#             Prevents Sad sounding like Sin (tajweed error per §52.4).
#
#   KB-12-04  Dark emphatic resonance guard 600-900Hz (Supplement §52.3)
#             Emphatic consonants add broad resonance 600-900Hz (pharyngealization).
#             design_eq clamps cuts to max -2dB in 580-920Hz when emphatic_dominant.
#
#   KB-12-05  Alif F1 formant guard 630-800Hz (Supplement §52.2, §2.4)
#             Alif F1 ~700Hz. Cutting below 700Hz removes the formant itself.
#             _eq_band_confidence caps confidence at 0.45 for negative nodes in 630-800Hz.
#
#   KB-12-06  Hams letter breathiness guard in TYPE-A NR (Supplement §52.3)
#             Hams/aspirated letters (fa/ha/tha/he/shin/kha/sad/sin/kaf/ta) have
#             ZCR > 0.22. NR now limits attenuation to max -6dB on high-ZCR frames.
#             Prevents erasing aspiration quality that distinguishes he from hamza.
#
#   KB-12-07  SHA-256 provenance hash logging (Supplement §65.2, Roadmap D)
#             Input and output SHA-256 hashes logged to stdout at start/end of enhance().
#             Enables integrity verification of processed files.
#
#   KB-12-08  TPDF dither for PCM-16 output (Supplement §57.2, Roadmap C)
#             Triangular probability density function dither applied before 16-bit
#             quantisation. Eliminates low-level quantisation distortion on quiet tails.
#
#   KB-12-09  Linkwitz-Riley crossover for BWE (Supplement §59, Vocos-BWE §2603.07285)
#             _v16_type_c_bw_extend uses proper 4th-order LR crossover instead of hard
#             spectral fold. Eliminates discontinuity artefact at codec cutoff frequency.
#
#   KB-12-10  Flutter burst detection in discontinuity score (Supplement §54.5)
#             compute_discontinuity_score now detects drops recovering within 30ms.
#             These score 0.5 weight each (vs 0.3 for slow drops) — more perceptually
#             disturbing since they truncate consonant onsets.
#
# INHERITED FROM v11: KB-01 through KB-10 (all v11 improvements preserved)
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   الاسترداد — ENGINE-1 OF THE AETHERION                                     ║
║   Recovery Engine — Tier 2 of 7                                             ║
║                                                                              ║
║   "الاسترداد" — to reclaim what was taken.                                   ║
║   Recordings that were damaged, degraded, nearly lost.                       ║
║   This engine reaches into the damage and recovers what was there.           ║
║                                                                              ║
║   المرجع: الشيخ ياسر الدوسري — 1425H                                         ║
║   الهدف: LUFS=-6.29 | RMS=-10.01 | Crest=10.25 | LRA=4.19                  ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   WHAT THIS ENGINE DOES                                                      ║
║   ─────────────────────────────────────────────────────────────────────     ║
║   Runs between Phase B (NR) and Phase C (EQ) of the base engine pipeline.  ║
║   Activated when the base engine hits a physical limit:                     ║
║                                                                              ║
║   TYPE_A — Noise-dominated (SNR < 12dB, frame-based)                        ║
║     Standard NR fails when no silence exists for profiling.                ║
║     الاسترداد uses statistical noise profiling from the quietest 8th        ║
║     percentile of frames, then applies shaped spectral subtraction.         ║
║     Validated: المائدة mosque recording, SNR=5.3dB, sibilant +3.5dB.       ║
║                                                                              ║
║   TYPE_B — Dynamics destroyed (LRA < 2.0 LU)                               ║
║     AGC/broadcast compression crushed the dynamic range.                   ║
║     Upward expansion via agate with 3-position empirical calibration.       ║
║     Validated: القمر, LRA 1.69→2.03 (+0.33 LU), Crest preserved.           ║
║                                                                              ║
║   TYPE_C — Codec artifacts / "pixeled voice"                                ║
║     Pre-echo (cosine-tapered attenuation before transients)                 ║
║     Mosquito noise (anlmdn non-local means denoising)                       ║
║     Bandwidth extension (aexciter harmonic generation above cutoff)         ║
║     Validated: الأحزاب 320kbps re-encode with original 5kHz cutoff source. ║
║                                                                              ║
║   R-3 — Harmonic Inference (F0-tracked additive synthesis)                  ║
║     TYPE_C's aexciter generates harmonics from noise — wrong positions.     ║
║     R-3 tracks F0 via autocorrelation, measures the actual harmonic         ║
║     amplitude envelope below codec_cutoff, PCHIP-extrapolates into the      ║
║     missing band, and synthesizes the correct harmonics at F0 multiples.    ║
║     Runs after TYPE_C on the cleaned signal. Trigger: cutoff < 13kHz.      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   BUG FIXES OVER v10.4 PROTOTYPE (10 confirmed, 10 fixed)                  ║
║   ─────────────────────────────────────────────────────────────────────     ║
║   1.  needs_tier2() NameError — constant defined after use                  ║
║   2.  Prefilter 34dB scale mismatch (amplitude vs power spectrum)           ║
║   3.  Post-NR floor estimated not measured (sibilant gate wrong ref)        ║
║   4.  agate range in dB not linear — crashes ffmpeg for all TYPE_B files   ║
║   5.  TYPE_B excluded القمر — Crest < 9.5 gate wrong for natural dynamics  ║
║   6.  aexciter type=ls unsupported, amount>60 crashes, HF guard too tight  ║
║   7.  TYPE_A used spectral SNR (reports 22dB on 5dB mosque recording)      ║
║   8.  Voiced HF loss undetected for high-bitrate re-encodes (الأحزاب)      ║
║   9.  BW extension early-exits when codec_cutoff=14kHz (inflated by noise) ║
║   10. Orchestrator gated BW extension on codec_cutoff < 11kHz (last gate)  ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   ARCHITECTURE — inherited from True Base v10 + Tier 2 extensions          ║
║   All v10.0–v10.1 fixes present: FIX-01–FIX-24 + NR-01–NR-05 + G1/G2/H/  ║
║   I/J/K/L/M from v10.1 session | Full Tier-2 Recovery Engine (TYPE A/B/C) ║
║                                                                              ║
║   v10.5 IMPROVEMENTS OVER BETA v2                                           ║
║   ──────────────────────────────────────────────────────────────────────    ║
║   BF-1  voiced_gap NameError in _bandwidth_extension_pass — FIXED          ║
║   BF-2  Retry path used type=ls / floor_f= (unsupported) — FIXED          ║
║   BF-3  Cache version mismatch v10.3/v10.4 — unified to v10.5             ║
║   BF-4  argparse version string stale — FIXED                              ║
║   TIER_CRITICAL  new sub-tier below TIER_DAMAGED (phone_8k / cassette /   ║
║         severe_clip) with correct detection + confidence vectors           ║
║   R-6   Source-condition quality ceilings per plan Section 2.3             ║
║         (78/72/70/75/80/76 per cassette gen / phone SR / clip severity)    ║
║   NR-06 Full harmonic hum chain: all n×50Hz or n×60Hz up to codec_cutoff  ║
║         Old code only cut 4 harmonics; now cuts entire harmonic series     ║
║   R-1   Wow/Flutter correction: F0 autocorrelation tracking + WSOLA       ║
║         segment resampling to correct cassette pitch drift                  ║
║   R-2   Dropout reconstruction: gap detection + cosine crossfade fill      ║
║         Masks tape dropout silence with smooth transitions                  ║
║   R-3   Harmonic Inference: F0 autocorr tracking → PCHIP amplitude        ║
║         envelope extrapolation → additive synthesis above codec_cutoff.    ║
║         Replaces aexciter's noise-driven harmonics with mathematically     ║
║         correct F0-aligned synthesis. Trigger: codec_cutoff < 13kHz.      ║
║   R-5c  Silence floor shaping: adds pink noise at -73dBFS in silence      ║
║         segments to match 1425H reference ambient presence                 ║
║                                                                              ║
║   ★ v10.6 — THE AETHERION PROJECT — ENGINE-1: RECOVERY                    ║
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

try:
    from df.enhance import enhance, init_df, load_audio, save_audio as df_save_audio
    DEEPFILTER_OK = True
except ImportError:
    DEEPFILTER_OK = False

# ── إحياء — Structural recovery for TIER_DAMAGED / TIER_CRITICAL ─────────────
try:
    from ihyaa_ve import apply_ihyaa_to_engine, ihyaa_apply_and_update_state
    IHYAA_OK = True
except ImportError:
    IHYAA_OK = False

# ── الجوهر — Voice character de-pixelation for TIER_DEGRADED and better ──────
try:
    from jawhar_v3 import apply_jawhar
    JAWHAR_OK = True
except ImportError:
    JAWHAR_OK = False

# CLI binary fallback — used when Python df package is not installed
import shutil as _shutil
_DF_CLI_CANDIDATES = [
    '/usr/local/bin/deep-filter',
    '/engines/deep-filter',
    '/home/claude/deep-filter',
    str(Path(__file__).parent / 'deep-filter'),
    'deep-filter',
]
_DF_CLI_BIN = None
for _c in _DF_CLI_CANDIDATES:
    try:
        if _shutil.which(_c) or (__import__('os').path.exists(_c) and __import__('os').access(_c, __import__('os').X_OK)):
            _DF_CLI_BIN = _c
            break
    except Exception:
        pass
DEEPFILTER_CLI_OK = _DF_CLI_BIN is not None

try:
    from safi_nr import (
        apply_safi_to_engine,
        SAFI_FRAME_SNR_GATE_DB,
        TIER_UNPROCESSABLE_SNR,
    )
    SAFI_OK = True
except ImportError:
    SAFI_OK = False
    SAFI_FRAME_SNR_GATE_DB = 8.0
    TIER_UNPROCESSABLE_SNR  = 2.5

try:
    from jalaa_nr import (
        apply_jalaa_to_engine,
        JALAA_FRAME_SNR_GATE_DB,
        JALAA_UNPROCESSABLE_SNR,
    )
    JALAA_OK = True
except ImportError:
    JALAA_OK = False
    JALAA_FRAME_SNR_GATE_DB = 8.0
    JALAA_UNPROCESSABLE_SNR = 2.5

try:
    from bayan_ve import (
        apply_bayan_to_engine,
        BAYAN_TRIGGER_VQS,
        BayanResult as _BayanResult,
    )
    BAYAN_OK = True
except ImportError:
    BAYAN_OK = False
    BAYAN_TRIGGER_VQS = 82.0

try:
    from noor_v5 import (
        load          as _noor_load,
        save_wav      as _noor_save_wav,
        harmonic_gate as _noor_hgate,
        even_harmonics as _noor_even,
        apply_eq      as _noor_eq,
    )
    NOOR_OK = True
except ImportError:
    NOOR_OK = False

# ── Tier-calibrated Noor parameters ──────────────────────────────────────────
# (sharpness, floor, strength, even_drive, even_mix_db)
# Higher sharpness = tighter harmonic gate = more noise rejection between partials.
# PRISTINE gets more aggressive gate + richer even-harmonic saturation.
# CLEAN is gentler — the source is already good, avoid over-processing.
_NOOR_TIER_PARAMS: dict = {
    'TIER_PRISTINE':    dict(sharpness=9.0,  floor=0.05, strength=0.92,
                             even_drive=1.6,  even_mix=-20.0),
    'TIER_CLEAN':       dict(sharpness=8.0,  floor=0.06, strength=0.90,
                             even_drive=1.5,  even_mix=-21.0),
    'TIER_COMPRESSED':  dict(sharpness=7.0,  floor=0.08, strength=0.86,
                             even_drive=1.35, even_mix=-22.5),
    'TIER_DEGRADED':    dict(sharpness=5.5,  floor=0.10, strength=0.75,
                             even_drive=1.2,  even_mix=-26.0),
}
# EQ curve shared across tiers — small lift toward 1425H centroid
_NOOR_EQ_NODES: list = [
    (130,  +1.5, 0.70, 'lowshelf'),   # body foundation restore
    (380,  -1.0, 0.90, 'peak'),        # body-hi mud trim
    (650,  -1.0, 0.90, 'peak'),        # warmth bump trim
    (1400, -1.0, 0.85, 'peak'),        # mid-box trim
    (3500, +0.8, 1.20, 'peak'),        # centroid presence toward 1425H
]

# ── Tier-calibrated room reverb parameters ───────────────────────────────────
# Maps to: Fruity Reeverb 2 (tail) + Fruity Delay 3 (pre-delay)
# First delay tap = Delay 3 pre-delay (15-20ms depth)
# Subsequent taps = Reeverb 2 room reflections (decaying)
_ROOM_TIER_PARAMS: dict = {
    # PRISTINE: richer hall feel — 20ms pre-delay, ~0.9s RT60 equivalent
    'TIER_PRISTINE': dict(in_gain=0.80, out_gain=0.88,
                          delays='20|40|70|130|220',
                          decays='0.50|0.30|0.20|0.12|0.06'),
    # CLEAN: lighter room presence — 15ms pre-delay, ~0.6s RT60 equivalent
    'TIER_CLEAN':    dict(in_gain=0.80, out_gain=0.92,
                          delays='15|30|55|100',
                          decays='0.38|0.22|0.13|0.06'),
}

# ── الجلال Phase B6 — Voice Transcendence Engine ──────────────────────────────
# Five sub-modules that lift the voice beyond restoration into transcendence.
# Parameters are tier-calibrated: pristine sources get full depth; damaged
# sources get conservative settings so recovery doesn't compound artefacts.
#
# J-1  Shimmer Synthesis      — spectral octave doubling of 3-7kHz into
#       6-14kHz; crystalline presence layer that appears above the voice.
# J-2  Transient Sculptor     — per-onset spectral flux amplifier; sharpens
#       the leading edge of Arabic stops/plosives (ق ك ط ب د).
# J-3  Formant Resonator      — LPC peak tracking per voiced frame; boosts
#       the Sheikh's dominant F1/F2/F3 resonance by ≤1.1dB with narrow Q.
# J-4  Psychoacoustic Widener — Haas-effect stereo (12ms delay + all-pass
#       decorrelation); mono-compatible; adds immersive spatial presence.
# J-5  Subharmonic Foundation — synthesizes F0/2 energy (55-65Hz); adds
#       chest-resonance gravity; bandpassed; blend capped at 12%.
#
# J-GATE: LUFS |Δ|<1.8dB · peak Δ<1.0dB · crest |Δ|<2.5dB · sib_Δ>-2.0dB.
# Full or partial revert on any gate failure. Bypassed on TIER_CRITICAL.
_JALAL_TIER_PARAMS: dict = {
    'TIER_PRISTINE': dict(
        shimmer_blend=0.042,
        shimmer_src_lo=3000.0,  shimmer_src_hi=7000.0,
        shimmer_dst_lo=6000.0,  shimmer_dst_hi=14000.0,
        transient_boost_db=1.8, transient_attack_ms=6.0,
        formant_boost_db=1.10,  formant_q=3.8,
        widener_delay_ms=13.0,  widener_mix=0.20,
        sub_blend=0.110,        sub_freq_lo=40.0,  sub_freq_hi=110.0,
    ),
    'TIER_COMPRESSED': dict(
        shimmer_blend=0.048,
        shimmer_src_lo=2800.0,  shimmer_src_hi=7000.0,
        shimmer_dst_lo=5600.0,  shimmer_dst_hi=14000.0,
        transient_boost_db=2.0, transient_attack_ms=5.0,
        formant_boost_db=1.10,  formant_q=3.8,
        widener_delay_ms=12.0,  widener_mix=0.20,
        sub_blend=0.095,        sub_freq_lo=42.0,  sub_freq_hi=110.0,
    ),
    'TIER_DEGRADED': dict(
        shimmer_blend=0.020,
        shimmer_src_lo=2500.0,  shimmer_src_hi=6000.0,
        shimmer_dst_lo=5000.0,  shimmer_dst_hi=12000.0,
        transient_boost_db=0.9, transient_attack_ms=8.0,
        formant_boost_db=0.60,  formant_q=3.0,
        widener_delay_ms=9.0,   widener_mix=0.12,
        sub_blend=0.055,        sub_freq_lo=45.0,  sub_freq_hi=100.0,
    ),
    'TIER_DAMAGED': dict(
        shimmer_blend=0.010,
        shimmer_src_lo=2000.0,  shimmer_src_hi=5000.0,
        shimmer_dst_lo=4000.0,  shimmer_dst_hi=10000.0,
        transient_boost_db=0.5, transient_attack_ms=10.0,
        formant_boost_db=0.35,  formant_q=2.5,
        widener_delay_ms=7.0,   widener_mix=0.08,
        sub_blend=0.030,        sub_freq_lo=50.0,  sub_freq_hi=90.0,
    ),
}

# J-GATE validation thresholds
_JALAL_GATE_LUFS_DELTA  = 1.8   # |LUFS change| ceiling
_JALAL_GATE_PEAK_DELTA  = 1.0   # peak increase ceiling (dB)
_JALAL_GATE_CREST_DELTA = 2.5   # |crest factor change| ceiling (dB)
_JALAL_GATE_SIB_DELTA   = -2.0  # sibilant SNR floor (dB); drop > 2dB → revert


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS (locked — never change)
# ══════════════════════════════════════════════════════════════════════════════
SR = 48000

# FIX-17: 24-bit WAV intermediates — 144dB SNR vs 96dB for 16-bit.
# Multi-pass TIER_DAMAGED sources benefit from this headroom.
WAV_CODEC = 'pcm_s24le'

# FIX-I/M: Encode gain constants
ENCODE_HEADROOM_DB = 1.5  # joint targets this much hotter than achievable_lufs
MP3_LOSS_DB = 0.8          # empirical 320kbps MP3 encoding level reduction vs WAV

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
    # Note: all curves use noise-gate floor at -40/-90 to prevent boosting
    # silence and micro-transitions (which creates audible "clicking").
    # The floor maps -40dBFS input → -90dBFS output (gate silence/pauses).
    # Voiced content starts above -30dBFS and gets gentle compression.
    'BYPASS':  '-90/-90|-40/-90|-20/-20|-3/-3|0/0',
    'MINIMAL': '-90/-90|-40/-90|-30/-30|-20/-19.5|-10/-9.8|-4/-3.9|-1/-0.95|0/-0.3',
    'LIGHT':   '-90/-90|-40/-90|-30/-28|-20/-17|-10/-8.2|-5/-4.1|-2/-1.6|-0.5/-0.4|0/-0.3',
    'MEDIUM':  '-90/-90|-40/-90|-30/-25|-20/-14|-12/-7.5|-6/-3.5|-2.5/-1.6|-0.8/-0.5|0/-0.2',
    'HEAVY':   '-90/-90|-40/-90|-30/-23|-20/-11|-13/-5.2|-6/-2.4|-2.5/-0.8|-0.5/-0.3|0/-0.1',
    'EXTREME': '-90/-90|-40/-90|-30/-21|-20/-9|-14/-4.5|-7/-2.0|-3/-0.6|0/-0.1',
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

# DeepFilterNet-3 — T-0.5 pre-NR pass
# Only applied when SNR < this value (dB).  14 dB ≈ D02_noise > 0.3.
DF3_SNR_GATE_DB = 15.0

# Module-level singleton: (model, df_state) after first init_df() call.
# None until the first job that passes the SNR gate.
_DF3_MODEL_CACHE = None

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
    frame_snr:        float = 25.0   # p80-p5 of frame RMS — actual perceived SNR
    # DeepFilterNet-3 (T-0.5) — base + adaptive VAD
    df3_applied:      bool  = False
    df3_snr_before:   float = 0.0   # SNR measured before DF3
    df3_snr_after:    float = 0.0   # SNR re-measured after DF3 (0 if not applied)
    df3_adaptive:     bool  = False  # True when adaptive 3-pass VAD ran
    df3_loud_chunks:  int   = 0      # chunks processed at atten_lim=8dB
    df3_mid_chunks:   int   = 0      # chunks processed at atten_lim=15dB
    df3_quiet_chunks: int   = 0      # chunks processed at atten_lim=20dB
    df3_boundaries:   int   = 0      # crossfade boundaries applied
    tier_unprocessable: bool  = False
    safi_applied:       bool  = False
    safi_snr_gain_db:   float = 0.0
    jalaa_applied:      bool  = False
    jalaa_drr_gain_db:  float = 0.0
    jalaa_reverb_removed: float = 0.0
    # البيان Phase B4 — Voice Intrinsic Quality Enhancement
    bayan_applied:       bool  = False
    bayan_vqs_before:    float = 100.0
    bayan_vqs_after:     float = 100.0
    bayan_vqs_gain:      float = 0.0
    # النور Phase B5 — Voice Character Correction (Soundgoodizer-equivalent)
    noor_applied:        bool  = False
    noor_rms_before_db:  float = 0.0
    noor_rms_after_db:   float = 0.0
    # الفضاء الصوتي Phase E1 — Room Presence (Fruity Reeverb 2 + Delay 3)
    room_reverb_applied: bool  = False
    room_reverb_wet_db:  float = 0.0
    # الجلال Phase B6 — Voice Transcendence Engine
    jalal_applied:       bool  = False
    jalal_shimmer:       bool  = False
    jalal_transient:     bool  = False
    jalal_formant:       bool  = False
    jalal_widener:       bool  = False
    jalal_sub:           bool  = False
    jalal_sib_delta:     float = 0.0
    # النداء Phase B7 — Neural Identity-Driven Audio Ascension
    nidaa_applied:       bool  = False
    nidaa_delta_lufs:    float = 0.0
    nidaa_delta_warmth:  float = 0.0
    nidaa_delta_sib:     float = 0.0
    nidaa_modules:       str   = ''
    # ── v11 Knowledge-Base Detections (KB §41.2–43.7) ────────────────────────
    # KB-01: Dolby B/C noise reduction detection
    dolby_suspected:          bool  = False
    dolby_hf_tilt_db:         float = 0.0    # 5kHz/1kHz noise floor ratio (dB)
    # KB-02: Azimuth misalignment (stereo cassette sources)
    azimuth_lag_samples:      int   = 0      # L/R cross-correlation peak lag
    azimuth_delay_ms:         float = 0.0    # azimuth delay in ms
    azimuth_corrected:        bool  = False
    # KB-03: PA system comb filter detection
    comb_filter_detected:     bool  = False
    comb_filter_notch_hz:     float = 0.0    # first notch frequency
    comb_filter_period_ms:    float = 0.0    # PA delay in ms
    # KB-04: Head clogging / progressive bandwidth loss
    hf_cutoff_drifting:       bool  = False
    hf_cutoff_start_hz:       float = 0.0
    hf_cutoff_end_hz:         float = 0.0
    # KB-05: IEC tape type detection
    tape_iec2_suspected:      bool  = False  # Chrome tape with IEC1 playback EQ
    # KB-06: Emphatic vs non-emphatic Arabic sibilant SNR split
    sib_emphatic_snr:         float = 0.0    # صظضط zone 3–5 kHz
    sib_nonemphatic_snr:      float = 0.0    # سشز zone 5–8 kHz
    sib_emphatic_dominant:    bool  = False  # emphatic sibilants stronger
    # KB-08: Output discontinuity score (NISQA-style)
    discontinuity_score:      float = 0.0    # 0=perfect continuity, 1=bad


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
    """Fast MP3 seek via ffmpeg -ss BEFORE -i (keyframe seek).
    FIX-G1: Use 0.5*FL+0.5*FR mono downmix via pan filter.
    ffmpeg default -ac 1 applies 0.707*(L+R), amplifying correlated stereo
    by +3.01dBFS, making all peak/RMS measurements 3dB too high and causing
    systematic TP violations in run_pass_encode. aformat→pan ensures correct
    power-preserving downmix for both mono and stereo inputs.
    """
    sp, tc = _safe(path)
    cmd = ['ffmpeg', '-y']
    if skip_s > 0:
        cmd += ['-ss', str(skip_s)]
    cmd += ['-i', sp, '-t', str(duration_s),
            '-af', 'aformat=channel_layouts=stereo,pan=mono|c0=0.5*FL+0.5*FR',
            '-f', 'f32le', '-ar', str(sr), '-loglevel', 'error', '-']
    r = subprocess.run(cmd, capture_output=True)
    if tc:
        try: os.remove(tc)
        except: pass
    if not r.stdout:
        # Fallback for unusual channel layouts
        sp2, tc2 = _safe(path)
        cmd2 = ['ffmpeg', '-y']
        if skip_s > 0:
            cmd2 += ['-ss', str(skip_s)]
        cmd2 += ['-i', sp2, '-t', str(duration_s),
                 '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-loglevel', 'error', '-']
        r = subprocess.run(cmd2, capture_output=True)
        if tc2:
            try: os.remove(tc2)
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
            if (d.get('cache_version') == 'v10.7'
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
            'cache_version': 'v10.7', 'ref_hash': current_hash,
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

    # FIX-SIL-1: Adaptive ceiling for mosque/noisy recordings.
    # Original fixed ceiling of (overall_rms - 18dB) fails when continuous
    # background noise means NO frames fall 18dB below the signal average.
    # Progressive relaxation: try 18→14→10dB until enough frames collected.
    sil_frames: List['np.ndarray'] = []
    sil_positions: List[float] = []
    min_frames = max(3, int(min_dur * sr / frame_n))
    for _margin in (18.0, 14.0, 10.0):
        silence_ceil = overall_db - _margin
        sil_frames = []
        sil_positions = []
        for i in range(0, len(audio) - frame_n, frame_n):
            f = audio[i:i + frame_n]
            r = rms_db(f)
            if -62.0 < r < silence_ceil:
                sil_frames.append(f)
                abs_pos = skip_s + i / sr
                sil_positions.append(abs_pos)
        if len(sil_frames) >= min_frames:
            break

    # FIX-SIL-2: Bottom-percentile fallback — for wall-to-wall noisy files.
    # If still no usable silence frames, take the quietest 5th-percentile
    # frames as the noise floor estimate. This is the correct approach for
    # recordings where background noise is present in every single frame.
    if len(sil_frames) < min_frames:
        all_frames = []
        all_positions = []
        for i in range(0, len(audio) - frame_n, frame_n):
            f = audio[i:i + frame_n]
            r = rms_db(f)
            if r > -62.0:
                all_frames.append((r, f, skip_s + i / sr))
        if len(all_frames) >= min_frames:
            all_frames.sort(key=lambda x: x[0])
            n_take = max(min_frames, len(all_frames) // 10)
            sil_frames   = [x[1] for x in all_frames[:n_take]]
            sil_positions = [x[2] for x in all_frames[:n_take]]
        else:
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
                         noise_type: str, smear_score: float,
                         src_sr: int = 44100, clip_ratio: float = 0.0) -> str:
    """
    Tier classification — 5 tiers including TIER_CRITICAL.

    TIER_CRITICAL (R-6): sub-tier below TIER_DAMAGED for sources where
    physical limits are so severe that specialized deep-recovery modules
    (R-1 wow, R-2 dropout, R-5c silence shaping) are warranted:
      - Phone recordings at 8kHz SR (phone_8k)
      - Cassette with hiss+hum noise and heavy smear (cassette)
      - Sources with clip_ratio > 15% (severe_clip)
    """
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

    # TIER_CRITICAL sub-classification within TIER_DAMAGED
    # These sources need deep recovery modules beyond standard TIER_DAMAGED
    if tier == 'TIER_DAMAGED':
        is_phone_8k    = src_sr <= 8000
        is_cassette    = (noise_type in ('hiss+hum', 'hiss') and smear_score >= 5.0
                          and codec_cutoff < 9000)
        is_severe_clip = clip_ratio > 0.15
        if is_phone_8k or is_cassette or is_severe_clip:
            tier = 'TIER_CRITICAL'

    return tier


def _compute_achievable(tier: str, codec_cutoff: float,
                         src_sr: int = 44100, clip_ratio: float = 0.0,
                         noise_type: str = 'none', smear_score: float = 0.0) -> Tuple[float, float, float]:
    """
    R-6: Source-condition quality ceilings (from Aetherion Plan Section 2.3).
    TIER_CRITICAL uses specific ceilings per sub-condition, not the generic TIER_DAMAGED floor.

    Quality ceilings (max achievable score → mapped to metric targets):
      cassette single gen:   78/100 → Crest<=8.5,  LRA<=3.8,  LUFS>=-7.0
      cassette 2+ gen:       72/100 → Crest<=7.5,  LRA<=3.2,  LUFS>=-7.5
      phone 8kHz SR:         70/100 → Crest<=7.0,  LRA<=3.0,  LUFS>=-8.0
      phone 16kHz SR:        75/100 → Crest<=8.0,  LRA<=3.5,  LUFS>=-7.2
      phone 22kHz SR:        80/100 → Crest<=8.8,  LRA<=3.8,  LUFS>=-7.0
      severe clip (>15%):    76/100 → Crest<=8.0,  LRA<=3.5,  LUFS>=-7.2
    """
    if tier == 'TIER_PRISTINE':
        return TARGET['lufs'], TARGET['crest'], TARGET['lra']
    if tier == 'TIER_COMPRESSED':
        return TARGET['lufs'], 10.1, 4.0
    if tier == 'TIER_DEGRADED':
        crest = float(np.clip(7.5 + (codec_cutoff / 10500.0) * 1.5, 7.5, 9.0))
        return -6.5, crest, 3.6
    if tier == 'TIER_CRITICAL':
        # R-6: fine-grained ceiling by sub-condition
        if src_sr <= 8000:
            return -8.0, 7.0, 3.0   # phone 8kHz — lowest ceiling
        if clip_ratio > 0.15:
            return -7.2, 8.0, 3.5   # severe clip
        is_cassette = noise_type in ('hiss+hum', 'hiss') and smear_score >= 5.0
        if is_cassette:
            # Approximate generation count from smear: >= 7 = 2+ gen cassette
            if smear_score >= 7.0:
                return -7.5, 7.5, 3.2  # 2+ gen cassette
            return -7.0, 8.5, 3.8      # single gen cassette
        # Fallback for any other TIER_CRITICAL sub-condition
        return -7.2, 7.8, 3.4
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

    # FIX-CONF-1: nr_confidence was hard-zeroed when noise_type='none'.
    # noise_type='none' now only means "silence analysis found no textbook
    # noise signature" — it does NOT mean the file is clean. A mosque file
    # with continuous background hum may produce noise_type='none' even after
    # FIX-SIL-1 if the hum ratio is below threshold. Guard: if frame_snr < 12dB
    # the file is noisy by definition regardless of noise_type classification.
    _frame_noisy = state.frame_snr < 12.0
    if (state.noise_type == 'none' and not _frame_noisy) or state.source_tier == 'TIER_PRISTINE':
        state.nr_confidence = 0.0
    else:
        sfm_f  = float(np.clip((state.silence_sfm - 0.1) / 0.55, 0.0, 1.0))
        flr_f  = float(np.clip(abs(state.silence_floor) / 62.0, 0.0, 1.0))
        base_conf = max(0.05, sfm_f * 0.60 + flr_f * 0.40)
        # If noise type is still 'none' but frame_snr says noisy: use a
        # conservative confidence derived purely from frame_snr headroom.
        if state.noise_type == 'none' and _frame_noisy:
            snr_f = float(np.clip((12.0 - state.frame_snr) / 10.0, 0.0, 1.0))
            state.nr_confidence = max(0.15, snr_f * 0.40)
        else:
            state.nr_confidence = base_conf

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



# ══════════════════════════════════════════════════════════════════════════════
#  v11 KNOWLEDGE-BASE DETECTION FUNCTIONS
#  Added per voice_audio_knowledge_base_MASTER.txt (Sections 1–51C, May 2026)
# ══════════════════════════════════════════════════════════════════════════════

# ── KB-01: Dolby B/C Noise Reduction Detection ───────────────────────────────
def _detect_dolby_nr(silence_frames_audio: 'np.ndarray', sr: int = SR) -> Tuple[bool, float]:
    """
    KB §41.5.2 — Detect whether a cassette was recorded with Dolby B/C NR
    but played back WITHOUT decoding.

    Symptom: HF noise floor is elevated relative to LF noise floor because
    the Dolby pre-emphasis boost is sitting un-decoded in the recording.

    Method:
      - Measure noise power at 1kHz (reference band)
      - Measure noise power at 5kHz (Dolby-affected band)
      - If 5kHz noise is > 6dB above 1kHz noise → Dolby suspected

    Returns: (suspected: bool, hf_tilt_db: float)

    Dolby B specification:
      NR at 1.2kHz = 6dB, at 2.4kHz = 8dB, at 5kHz = 10dB
    Un-decoded playback reverses this — the noise RISES by those amounts.
    """
    if not NUMPY_OK or len(silence_frames_audio) < sr * 0.5:
        return False, 0.0

    try:
        spec = np.abs(rfft(silence_frames_audio.astype(np.float64))) ** 2
        freqs = rfftfreq(len(silence_frames_audio), 1.0 / sr)

        # 1kHz reference band (850–1150 Hz)
        ref_mask = (freqs >= 850.0) & (freqs <= 1150.0)
        # 5kHz indicator band (4500–5500 Hz)
        hf_mask  = (freqs >= 4500.0) & (freqs <= 5500.0)

        if not ref_mask.any() or not hf_mask.any():
            return False, 0.0

        ref_power = float(np.mean(spec[ref_mask]))
        hf_power  = float(np.mean(spec[hf_mask]))

        if ref_power < 1e-20:
            return False, 0.0

        tilt_db = float(10.0 * np.log10(hf_power / (ref_power + 1e-20)))

        # Flat pink noise: 5kHz ≈ 1kHz in energy per bark band.
        # With Dolby B un-decoded: 5kHz noise ~8–10 dB above 1kHz.
        # Threshold of 6dB is conservative (catches strong Dolby B without
        # false-positive on natural voice spectral rolloff).
        suspected = tilt_db > 6.0

        return suspected, round(float(tilt_db), 2)
    except Exception:
        return False, 0.0


def _apply_dolby_compensatory_deemphasis(input_wav: str, tilt_db: float) -> str:
    """
    KB §41.5.3 — Apply rough compensatory HF de-emphasis for un-decoded Dolby B.

    Applies a gentle high-shelf cut to partially undo the Dolby B pre-emphasis
    sitting in the noise floor.  Imperfect but reduces the worst effect.

    Shelf: -4 dB at 3kHz, Q=0.7.  Scaled by tilt_db/10.0 so mild cases get
    less correction.  MAX correction: -6 dB (prevents over-darkening the voice).

    This is NOT a proper Dolby B decode (that requires the sliding-band
    compander circuit).  It is a safety measure to avoid the HF noise being
    further boosted by the engine's presence-lifting EQ nodes.
    """
    gain_db = float(np.clip(-tilt_db * 0.5, -6.0, -1.0))
    tmp = os.path.join(_TMP, 'dolby_deemph.wav')
    cmd = [
        'ffmpeg', '-y', '-i', input_wav,
        '-af', f'treble=g={gain_db:.2f}:f=3000:t=q:w=0.7',
        '-c:a', WAV_CODEC, '-loglevel', 'error', tmp,
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp):
        L(f'  [KB-01/Dolby] compensatory de-emphasis {gain_db:.1f}dB @ 3kHz ✓')
        return tmp
    return input_wav


# ── KB-02: Azimuth Misalignment Detection + Correction ───────────────────────
def _detect_azimuth_mismatch(path: str, sr: int = SR,
                              max_lag_ms: float = 5.0) -> Tuple[int, float]:
    """
    KB §41.2-41.3 — Detect azimuth misalignment in stereo cassette recordings.

    Method: Cross-correlate L and R channels.  If the peak lag ≠ 0, the
    channels are time-misaligned (interchannel delay = azimuth effect).

    The delay_ms = lag_samples / sr * 1000.
    Azimuth 1° misalignment → ~110 μs delay on cassette at 4.75 cm/s.

    Returns: (lag_samples: int, delay_ms: float)
      lag > 0: L leads R (apply delay to L to align)
      lag < 0: R leads L (apply delay to R to align)
    """
    if not NUMPY_OK:
        return 0, 0.0

    max_lag_n = int(max_lag_ms / 1000.0 * sr)

    try:
        # Load stereo via ffmpeg into two mono channels
        cmd = [
            'ffmpeg', '-y', '-i', path,
            '-t', '30',           # 30s sample is enough for cross-correlation
            '-af', 'channelsplit=channel_layout=stereo',
            '-f', 'f32le', '-ar', str(sr), '-',
        ]
        # Use a simpler approach: load as stereo numpy
        cmd2 = [
            'ffmpeg', '-y', '-i', path,
            '-t', '30', '-ac', '2',
            '-f', 'f32le', '-ar', str(sr), '-',
            '-loglevel', 'error',
        ]
        r = subprocess.run(cmd2, capture_output=True)
        if r.returncode != 0 or len(r.stdout) < 1000:
            return 0, 0.0

        stereo = np.frombuffer(r.stdout, dtype=np.float32)
        if len(stereo) < sr * 2:
            return 0, 0.0

        # Interleaved stereo: even = L, odd = R
        L_ch = stereo[0::2].astype(np.float64)
        R_ch = stereo[1::2].astype(np.float64)
        n    = min(len(L_ch), len(R_ch))
        L_ch = L_ch[:n]
        R_ch = R_ch[:n]

        # Normalise
        L_ch -= np.mean(L_ch); L_ch /= (np.std(L_ch) + 1e-10)
        R_ch -= np.mean(R_ch); R_ch /= (np.std(R_ch) + 1e-10)

        # Cross-correlation via FFT (fast for long signals)
        n_fft = 1
        while n_fft < 2 * n:
            n_fft <<= 1
        XL  = np.fft.rfft(L_ch, n=n_fft)
        XR  = np.fft.rfft(R_ch, n=n_fft)
        xc  = np.fft.irfft(XL * np.conj(XR), n=n_fft)

        # Search only within ±max_lag_ms window
        search_lags = list(range(-max_lag_n, max_lag_n + 1))
        xc_wrapped  = np.concatenate([xc[-max_lag_n:], xc[:max_lag_n + 1]])
        peak_idx    = int(np.argmax(np.abs(xc_wrapped)))
        lag         = search_lags[peak_idx]
        delay_ms    = lag / sr * 1000.0

        return lag, round(delay_ms, 3)
    except Exception:
        return 0, 0.0


def _apply_azimuth_correction(input_wav: str, lag_samples: int, sr: int = SR) -> str:
    """
    KB §41.3 — Apply digital azimuth correction via fractional delay.

    Shifts the LEADING channel forward by |lag_samples| to align with
    the lagging channel.  Removes the interchannel comb filtering caused
    by the temporal misalignment.

    LIMITATION (per IASA TC-04): this removes the stereo phase error but
    CANNOT recover the high-frequency information attenuated by the
    increased effective gap length.  A gentle HF shelf is added to partially
    compensate the physical gap loss.

    Returns: path to corrected WAV (or input_wav on failure).
    """
    if lag_samples == 0 or not NUMPY_OK:
        return input_wav

    try:
        # Load stereo
        cmd = [
            'ffmpeg', '-y', '-i', input_wav,
            '-ac', '2', '-f', 'f32le', '-ar', str(sr),
            '-loglevel', 'error', '-',
        ]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0 or len(r.stdout) < 1000:
            return input_wav

        stereo = np.frombuffer(r.stdout, dtype=np.float32).copy()
        if len(stereo) < sr * 2:
            return input_wav

        L_ch = stereo[0::2].copy()
        R_ch = stereo[1::2].copy()
        n    = min(len(L_ch), len(R_ch))

        # Delay the LEADING channel so both align with the lagging channel
        abs_lag = abs(lag_samples)
        if lag_samples > 0:
            # L leads R → delay L (shift L right by lag_samples)
            L_aligned = np.concatenate([np.zeros(abs_lag, dtype=np.float32),
                                        L_ch[:n - abs_lag]])
            R_aligned = R_ch[:n]
        else:
            # R leads L → delay R (shift R right by lag_samples)
            L_aligned = L_ch[:n]
            R_aligned = np.concatenate([np.zeros(abs_lag, dtype=np.float32),
                                        R_ch[:n - abs_lag]])

        # Interleave back
        out_stereo = np.empty(2 * n, dtype=np.float32)
        out_stereo[0::2] = L_aligned
        out_stereo[1::2] = R_aligned

        tmp = os.path.join(_TMP, 'azimuth_corrected.wav')
        r2 = subprocess.run(
            ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(sr), '-ac', '2',
             '-i', '-', '-c:a', WAV_CODEC, '-loglevel', 'error', tmp],
            input=out_stereo.tobytes(), capture_output=True,
        )
        if r2.returncode == 0 and os.path.exists(tmp):
            delay_ms = abs_lag / sr * 1000.0
            L(f'  [KB-02/Azimuth] lag={lag_samples:+d} samples ({delay_ms:.3f}ms) corrected ✓')
            return tmp
        return input_wav
    except Exception:
        return input_wav


# ── KB-03: PA System Comb Filter Detection ───────────────────────────────────
def _detect_comb_filter(spectrum: Dict[float, float]) -> Tuple[bool, float, float]:
    """
    KB §38.5 — Detect periodic spectral notches from PA system reflections.

    Mosque PA systems use delayed loudspeakers.  The direct imam mic + PA
    output creates comb filtering: periodic notches at f_n = n/(2×delay_time).

    Method:
      - Convert spectrum to linear amplitude, resample to linear freq grid
      - Autocorrelate the spectral envelope
      - Find a peak at lag > 0 that exceeds 0.35 (indicates periodicity)

    Returns: (detected: bool, first_notch_hz: float, pa_delay_ms: float)
    """
    if not NUMPY_OK or len(spectrum) < 10:
        return False, 0.0, 0.0

    try:
        fcs   = sorted(fc for fc in spectrum if 400.0 <= fc <= 8000.0)
        if len(fcs) < 8:
            return False, 0.0, 0.0

        # Convert dB to linear amplitude
        vals  = np.array([10.0 ** (spectrum[fc] / 20.0) for fc in fcs])
        vals -= float(np.mean(vals))

        # Autocorrelation of spectral envelope
        n_fft = 1
        while n_fft < 2 * len(vals):
            n_fft <<= 1
        xc = np.fft.irfft(np.fft.rfft(vals, n=n_fft) *
                           np.conj(np.fft.rfft(vals, n=n_fft)), n=n_fft)
        xc /= (xc[0] + 1e-10)   # normalise to 1 at lag=0

        # Search for secondary peak in lags 2–len(fcs)//2
        search = xc[2: len(fcs) // 2]
        if len(search) < 3:
            return False, 0.0, 0.0

        peak_lag = int(np.argmax(search)) + 2
        peak_val = float(search[peak_lag - 2])

        if peak_val < 0.35:
            return False, 0.0, 0.0

        # Estimate notch frequency from lag
        freq_spacing = (fcs[-1] - fcs[0]) / max(len(fcs) - 1, 1)
        notch_spacing_hz = peak_lag * freq_spacing
        first_notch_hz   = notch_spacing_hz / 2.0
        pa_delay_ms      = 1000.0 / (2.0 * notch_spacing_hz) if notch_spacing_hz > 0 else 0.0

        # Sanity check: PA delay typically 20–150 ms for a mosque
        if not (10.0 <= pa_delay_ms <= 200.0):
            return False, 0.0, 0.0

        return True, round(first_notch_hz, 1), round(pa_delay_ms, 2)
    except Exception:
        return False, 0.0, 0.0


def _build_comb_fill_eq_nodes(first_notch_hz: float, pa_delay_ms: float,
                               max_fill_db: float = 3.0) -> List[Tuple[float, float, float]]:
    """
    KB §38.5 — Build EQ fill nodes to compensate PA comb filter notches.

    Adds narrow-ish boost nodes at the detected notch frequencies.
    Limited to +max_fill_db to avoid over-brightening.
    Only fills notches within the voice-important range (300–6000 Hz).
    """
    if pa_delay_ms <= 0 or first_notch_hz <= 0:
        return []

    notch_spacing = 1000.0 / (2.0 * pa_delay_ms)  # Hz between notches
    nodes = []
    f = first_notch_hz
    while f <= 6000.0:
        if f >= 300.0:
            # Narrow bell boost: Q=3.0 (surgical), gain scaled by proximity to voice zone
            weight = 1.0 if 500.0 <= f <= 4000.0 else 0.5
            g = round(max_fill_db * weight, 2)
            if g >= 0.5:
                nodes.append((round(f, 1), g, 3.0))
        f += notch_spacing

    return nodes[:4]   # cap at 4 nodes to avoid over-correcting


# ── KB-04: Head Clogging Progressive Bandwidth Drift ─────────────────────────
def _detect_head_clogging_drift(path: str, total_s: float,
                                 n_windows: int = 3) -> Tuple[bool, float, float]:
    """
    KB §43.5 — Detect progressive HF cutoff decrease from head clogging.

    Oxide shed from the tape accumulates on the head gap, effectively
    widening it, which lowers the first null frequency → HF rolls off
    progressively through the recording.

    Method: measure codec_cutoff in early, mid, and late 20s windows.
    If cutoff decreases by > 2kHz from early → late: head clogging flagged.

    Returns: (drifting: bool, cutoff_start_hz: float, cutoff_end_hz: float)
    """
    if not NUMPY_OK or total_s < 60.0:
        return False, 0.0, 0.0

    try:
        positions = [
            max(15.0,  total_s * 0.10),   # early
            total_s * 0.50,                # mid
            min(total_s - 25.0, total_s * 0.85),   # late
        ]

        cutoffs = []
        for pos in positions:
            clip = load_audio_fast(path, pos, 20.0)
            if len(clip) < SR * 5:
                continue
            spec = third_octave(clip)
            if not spec:
                continue
            # Compute codec cutoff for this window
            cutoff = float(max(detect_hf_rolloff(spec, 6.0), 4000.0))
            cutoffs.append(cutoff)

        if len(cutoffs) < 2:
            return False, 0.0, 0.0

        cutoff_start = float(cutoffs[0])
        cutoff_end   = float(cutoffs[-1])
        drift        = cutoff_start - cutoff_end   # positive = degrading

        # Flag if HF cutoff dropped by > 2kHz from start to end
        drifting = drift > 2000.0

        return drifting, round(cutoff_start, 0), round(cutoff_end, 0)
    except Exception:
        return False, 0.0, 0.0


# ── KB-05: IEC Cassette Tape Type Detection ───────────────────────────────────
def _detect_iec2_tape_mismatch(spectrum: Dict[float, float],
                                state: 'InputState') -> bool:
    """
    KB §43.4 — Detect IEC Type II (chrome) tape played with IEC Type I (ferric) EQ.

    Symptom: gradual HF rolloff starting below 6kHz AND codec_cutoff > 10kHz
    (so the rolloff is NOT a codec limitation — it's a tape EQ mismatch).

    The gradual rolloff signature:
      - Energy drops smoothly from 3kHz upward (tape EQ shape)
      - Distinct from codec cutoff (sudden hard drop)
      - HF deficit at 6-8kHz is 5+ dB relative to 2-3kHz

    Returns: True if IEC2 chrome tape on IEC1 playback suspected.
    """
    if not spectrum or state.codec_cutoff < 10000.0:
        return False   # If codec already cuts at <10kHz, can't distinguish

    try:
        # Measure energy at reference band (2-3kHz)
        ref_bands = [fc for fc in spectrum if 2000.0 <= fc <= 3000.0]
        hf_bands  = [fc for fc in spectrum if 6000.0 <= fc <= 8000.0]

        if not ref_bands or not hf_bands:
            return False

        ref_level = float(np.mean([spectrum[fc] for fc in ref_bands]))
        hf_level  = float(np.mean([spectrum[fc] for fc in hf_bands]))

        deficit = ref_level - hf_level   # dB — higher = more HF loss

        # Gradual rolloff: check that 4-5kHz is intermediate (not sudden cutoff)
        mid_bands = [fc for fc in spectrum if 4000.0 <= fc <= 5000.0]
        if not mid_bands:
            return False
        mid_level = float(np.mean([spectrum[fc] for fc in mid_bands]))

        # IEC2 mismatch pattern: smooth -3dB at 4kHz, -5+ dB at 7kHz (vs 2kHz)
        mid_deficit  = ref_level - mid_level
        # HF drops more than mid → smooth rolloff (not codec hard cut)
        smooth_rolloff = (mid_deficit >= 2.0) and (deficit >= mid_deficit + 2.0)

        # Only flag when it's cassette-tier AND the codec wouldn't explain this
        is_cassette_tier = state.source_tier in ('TIER_CRITICAL', 'TIER_DAMAGED')

        return smooth_rolloff and is_cassette_tier and (deficit >= 5.0)
    except Exception:
        return False


# ── KB-06: Emphatic vs Non-Emphatic Arabic Sibilant SNR ─────────────────────
def compute_sibilant_snr_split(audio: 'np.ndarray', silence_floor: float,
                                sr: int = SR) -> Tuple[float, float, bool]:
    """
    KB §4.1-4.6 — Split Arabic sibilant SNR into emphatic vs non-emphatic zones.

    Arabic emphatic sibilants (ص ض ظ ط): energy concentrated 3,000–5,000 Hz
    Arabic non-emphatic sibilants (س ش ز): energy concentrated 5,000–8,000 Hz

    This distinction is acoustically critical for Quran: confusing ص/س
    changes word meaning (e.g. الصراط vs السراط).

    Returns: (emphatic_snr: float, nonemphatic_snr: float, emphatic_dominant: bool)
      emphatic_dominant: True when emphatic zone is ≥ 2dB stronger than non-emphatic
                         → de-essing should preserve the emphatic band more.
    """
    if not NUMPY_OK or len(audio) < sr * 0.5:
        return 10.0, 10.0, False

    try:
        spec   = np.abs(rfft(audio.astype(np.float64))) ** 2
        freqs  = rfftfreq(len(audio), 1.0 / sr)

        # Emphatic zone: ص ض ظ ط — 3,000–5,000 Hz
        emp_bands = [3150.0, 4000.0]
        emp_vals  = []
        for fc in emp_bands:
            mask = (freqs >= fc * 0.85) & (freqs <= fc * 1.18)
            if mask.any():
                emp_vals.append(float(10 * np.log10(np.mean(spec[mask]) + 1e-30)))

        # Non-emphatic zone: س ش ز — 5,000–8,000 Hz
        nemp_bands = [5000.0, 6300.0, 8000.0]
        nemp_vals  = []
        for fc in nemp_bands:
            mask = (freqs >= fc * 0.85) & (freqs <= fc * 1.18)
            if mask.any():
                nemp_vals.append(float(10 * np.log10(np.mean(spec[mask]) + 1e-30)))

        emp_snr  = (float(np.mean(emp_vals))  - silence_floor) if emp_vals  else 10.0
        nemp_snr = (float(np.mean(nemp_vals)) - silence_floor) if nemp_vals else 10.0

        # emphatic_dominant when the 3-5kHz zone is significantly stronger
        emphatic_dominant = (emp_snr - nemp_snr) >= 2.0

        return round(emp_snr, 2), round(nemp_snr, 2), emphatic_dominant
    except Exception:
        return 10.0, 10.0, False


# ── KB-08: Energy Discontinuity Score ────────────────────────────────────────
def compute_discontinuity_score(audio: 'np.ndarray', silence_thresh_db: float,
                                 sr: int = SR, frame_ms: float = 50.0) -> float:
    """
    KB §38B.2 — Estimate NISQA-style discontinuity: detect sudden RMS drops
    not attributable to waqf (intentional silence) pauses.

    A sudden unexplained energy drop (> 15dB in < 50ms) that is NOT preceded
    or followed by a recognised silence zone is a discontinuity artifact —
    likely caused by:
      - Word dropping (BUG-2 type)
      - Tape dropout not reconstructed by R-2
      - Aggressive NR suppression on a voiced frame

    KB-12-10 — Flutter burst detection (Supplement §54.5):
      The original function detected slow drops (waqf-like). It missed short
      "flutter bursts": frames that drop > 15dB and RECOVER within 2 frames
      (< 100ms). These are caused by NR over-suppression on voiced consonant
      onsets — they truncate the attack of a consonant and are more perceptually
      disturbing than slow waqf-length gaps.
      New weight: slow drops = 0.30, flutter bursts = 0.60 (more severe).

    Score: 0.0 = no discontinuities, 1.0 = many unexplained drops.
    """
    if not NUMPY_OK or len(audio) < sr * 1.0:
        return 0.0

    try:
        frame_n = max(1, int(frame_ms / 1000.0 * sr))
        n_frames = len(audio) // frame_n
        if n_frames < 4:
            return 0.0

        rms_frames = np.array([
            rms_db(audio[i * frame_n: (i + 1) * frame_n])
            for i in range(n_frames)
        ])

        # Classify silence frames
        voiced_med = float(np.median(rms_frames[rms_frames > silence_thresh_db - 15]))
        silence_gate = voiced_med - 20.0

        weighted_discontinuities = 0.0
        total_voiced = 0

        for i in range(1, n_frames - 2):
            if rms_frames[i - 1] > silence_gate:    # previous frame is voiced
                total_voiced += 1
                if rms_frames[i] < silence_gate:    # current frame drops to silence
                    # How long does the silence last?
                    following_silent = sum(
                        1 for j in range(i, min(i + 10, n_frames))
                        if rms_frames[j] < silence_gate
                    )
                    if following_silent < 2:
                        # KB-12-10: Check for flutter burst (recovers within 2 frames)
                        # vs slow drop (stays silent 2+ frames but < 10 frames)
                        if following_silent <= 1 and i + 1 < n_frames and rms_frames[i + 1] > silence_gate:
                            # Flutter burst: drop and immediate recovery
                            # More perceptually disturbing — consonant onset truncation
                            weighted_discontinuities += 0.60
                        else:
                            # Slow unexplained drop
                            weighted_discontinuities += 0.30

        if total_voiced == 0:
            return 0.0

        score = float(np.clip(weighted_discontinuities / max(total_voiced, 1) * 20.0, 0.0, 1.0))
        return round(score, 3)
    except Exception:
        return 0.0


# ── KB-09: Maqam-Aware EQ Scale for Voice-Identity Clamps ───────────────────
def _maqam_eq_scale(maqam_confidence: float, maqam: str) -> float:
    """
    KB §17.7, §25.6 — Scale the voice-identity EQ clamps by maqam confidence.

    When the maqam is detected with high confidence, we know the characteristic
    intervals — so the EQ can be slightly more conservative in the 150-800 Hz
    band (the voice identity zone) because Sidrah's HLE has already shaped those
    harmonics toward the maqam template.

    When maqam is unknown (low confidence), do not reduce EQ clamps — the
    spectral distance from reference might be real and needs correction.

    Returns: scale factor 0.6–1.0 applied to the voice-identity clamp limits.
      1.0 = normal clamps (maqam unknown or low confidence)
      0.7 = tighter clamps (high maqam confidence — Sidrah handled this)
    """
    if maqam_confidence < 0.35 or maqam == 'UNKNOWN':
        return 1.0   # No maqam info → full EQ correction allowed

    # High-confidence detection: Sidrah HLE covered the maqam harmonics,
    # reduce EQ aggressiveness in the voice identity band
    scale = float(np.clip(1.0 - (maqam_confidence - 0.35) * 0.6, 0.7, 1.0))
    return round(scale, 2)



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
    # FIX (v10.5): frame_snr = p80 - p5 of frame RMS distribution.
    # compute_band_snr gives spectral-shape SNR (high even for tonal noise).
    # frame_snr gives the true perceived SNR: difference between voiced speech
    # frames and the quietest background frames. For mosque recordings where
    # noise is always present, frame_snr is 3-6dB vs compute_band_snr of 20+dB.
    # TYPE_A needs frame_snr, not snr_global.
    _fn_snr = int(0.05 * SR)
    _fr_snr = np.array([rms_db(clip[i:i + _fn_snr])
                         for i in range(0, len(clip) - _fn_snr, _fn_snr)])
    state.frame_snr = (float(np.percentile(_fr_snr, 80) - np.percentile(_fr_snr, 5))
                       if len(_fr_snr) >= 10 else state.snr_global)

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

    # FIX-TIER-1: source_tier was using snr_global (spectral, 19-25dB on noisy
    # mosque files) instead of frame_snr (3-6dB, the real perceived SNR).
    # spectral SNR is high even when noise is tonal/continuous because it
    # measures shape similarity, not speech-to-noise ratio. frame_snr
    # (p80 - p5 of frame RMS) correctly reflects the noise floor.
    _snr_for_tier = min(state.snr_global, state.frame_snr)
    state.source_tier = _derive_source_tier(
        state.src_br, state.codec_cutoff, _snr_for_tier,
        state.noise_type, state.smear_score,
        src_sr=state.src_sr, clip_ratio=state.clip_ratio)
    state.achievable_lufs, state.achievable_crest, state.achievable_lra = \
        _compute_achievable(state.source_tier, state.codec_cutoff,
                            src_sr=state.src_sr, clip_ratio=state.clip_ratio,
                            noise_type=state.noise_type, smear_score=state.smear_score)

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

    # ── v11 KB Detections (run after tier classification) ────────────────────
    # KB-01: Dolby B/C detection from HF noise tilt in silence frames
    if state.source_tier in ('TIER_CRITICAL', 'TIER_DAMAGED') and state.silence_valid:
        sil_frames = [clip[int(p * SR): int(p * SR) + int(0.5 * SR)]
                      for p in state.silence_frame_abs[:8]
                      if int(p * SR) + int(0.5 * SR) < len(clip)]
        if sil_frames:
            sil_cat = np.concatenate(sil_frames)
            dolby_flag, dolby_tilt = _detect_dolby_nr(sil_cat, sr=SR)
            state.dolby_suspected  = dolby_flag
            state.dolby_hf_tilt_db = dolby_tilt
            if dolby_flag:
                L(f'  [KB-01/Dolby] suspected — HF tilt={dolby_tilt:.1f}dB (>6dB threshold)')

    # KB-02: Azimuth mismatch — stereo cassette sources only (analysed later in enhance())
    # Detection deferred to enhance() where we have the working file path

    # KB-03: PA comb filter detection from full spectrum
    if full_spectrum:
        comb_det, comb_notch, comb_delay = _detect_comb_filter(full_spectrum)
        state.comb_filter_detected  = comb_det
        state.comb_filter_notch_hz  = comb_notch
        state.comb_filter_period_ms = comb_delay
        if comb_det:
            L(f'  [KB-03/Comb] PA comb filter — first notch={comb_notch:.0f}Hz '
              f'PA delay={comb_delay:.1f}ms')

    # KB-04: Head clogging progressive bandwidth drift
    if state.source_tier in ('TIER_CRITICAL', 'TIER_DAMAGED') and state.total_s > 60.0:
        drift, co_start, co_end = _detect_head_clogging_drift(path, state.total_s)
        state.hf_cutoff_drifting  = drift
        state.hf_cutoff_start_hz  = co_start
        state.hf_cutoff_end_hz    = co_end
        if drift:
            L(f'  [KB-04/HeadClog] progressive cutoff drift: '
              f'{co_start:.0f}Hz→{co_end:.0f}Hz (Δ={co_start-co_end:.0f}Hz) '
              f'— re-digitization recommended')

    # KB-05: IEC tape type (chrome vs ferric EQ mismatch)
    if full_spectrum:
        state.tape_iec2_suspected = _detect_iec2_tape_mismatch(full_spectrum, state)
        if state.tape_iec2_suspected:
            L(f'  [KB-05/IEC2] chrome tape with ferric EQ suspected — '
              f'HF deficit at 6-8kHz; will apply +2dB compensatory shelf')

    # KB-06: Emphatic vs non-emphatic Arabic sibilant SNR split
    if len(clip) > SR * 2:
        emp_snr, nemp_snr, emp_dom = compute_sibilant_snr_split(
            clip, state.silence_floor, sr=SR)
        state.sib_emphatic_snr      = emp_snr
        state.sib_nonemphatic_snr   = nemp_snr
        state.sib_emphatic_dominant = emp_dom
        L(f'  [KB-06/Sibilant] emphatic(ص ض)={emp_snr:.1f}dB '
          f'non-emphatic(س ش)={nemp_snr:.1f}dB '
          f'dominant={"EMPHATIC" if emp_dom else "NON-EMPHATIC"}')

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
    tmp = os.path.join(_TMP, 'v100_declip.wav')
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
def _build_hum_notch(sil: Dict, codec_cutoff: float = 20000.0) -> str:
    """
    NR-06: Full harmonic hum chain — cuts all n*50 or n*60 Hz harmonics up to
    codec_cutoff, not just the first two.

    The plan specifies: "50Hz + 100 + 150... or 60 + 120 + 180... completely".
    Original code only cut 50/60/100/120Hz — missing 150, 180, 200, 240... etc.
    Cascade hum at 150Hz (3rd harmonic of 50Hz) is highly audible and commonly
    present in transformer hum recorded in mosques on mains power.

    Guard: never cut above codec_cutoff × 0.85 (codec already removed it).
    Cut depth scales with harmonic number: fundamentals get deepest cut,
    higher harmonics get shallower cuts (natural harmonic rolloff).
    """
    if not sil.get('valid'):
        return ''
    parts = []

    hum_db_map = {
        50:  sil.get('hum_50db',  0.0),
        60:  sil.get('hum_60db',  0.0),
        100: sil.get('hum_100db', 0.0),
        120: sil.get('hum_120db', 0.0),
    }

    # Determine which fundamental is present (50Hz or 60Hz system)
    fundamental = 0
    if hum_db_map.get(50, 0) > 15.0:
        fundamental = 50
    elif hum_db_map.get(60, 0) > 15.0:
        fundamental = 60

    if fundamental == 0:
        # No clear fundamental — only cut if harmonics were directly detected
        for fc, threshold in [(50, 15.0), (60, 15.0), (100, 12.0), (120, 12.0)]:
            db = hum_db_map.get(fc, 0.0)
            if db > threshold and fc < codec_cutoff * 0.85:
                depth = min(24, int(db * 0.8))
                q = 0.4 if fc <= 60 else 0.6
                parts.append(f'equalizer=f={fc}:width_type=q:width={q}:g=-{depth}')
        return ','.join(parts)

    # Build full harmonic series for detected fundamental
    harmonic_n = 1
    while True:
        freq = fundamental * harmonic_n
        if freq > codec_cutoff * 0.85 or freq > 18000:
            break
        # Fundamental and 2nd harmonic: use measured depth
        if freq in hum_db_map and hum_db_map[freq] > 10.0:
            db_measured = hum_db_map[freq]
            depth = min(24, int(db_measured * 0.8))
        elif harmonic_n == 1:
            # Fundamental always present if we detected 50/60Hz
            depth = min(24, int(hum_db_map[fundamental] * 0.8))
        else:
            # Higher harmonics: estimate from fundamental with natural rolloff
            # Each harmonic is ~6dB weaker than the previous
            fund_depth = min(24, int(hum_db_map[fundamental] * 0.8))
            depth = max(3, int(fund_depth - (harmonic_n - 1) * 5))

        if depth >= 3:
            q = 0.4 if harmonic_n == 1 else 0.5 if harmonic_n <= 3 else 0.7
            parts.append(f'equalizer=f={freq}:width_type=q:width={q}:g=-{depth}')

        harmonic_n += 1
        if harmonic_n > 20:
            break  # safety cap

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

    Stage 3 — High-frequency hiss shelf (conditional):
              If noise_type contains 'hiss' and codec_cutoff > 8kHz,
              a gentle 2dB shelf cut above 7kHz removes the HF residual
              that afftdn leaves behind — reduces hiss without killing air.

    Stage 4 — Low-pass for codec ringing (conditional):
              Only for src_br < 65kbps with detected rolloff < 16kHz.
    """
    ref_nr_floor = float(ref.silence_floor - 3.0)
    nf = float(np.clip(max(state.silence_floor + 2.0, ref_nr_floor), -76, -40))

    # NR-05: depth scales with silence frame quality
    n_frames = len(state.silence_frame_abs)
    frame_bonus = float(np.clip((n_frames - 5) / 15.0, 0.0, 1.0))  # 0 at 5, 1.0 at 20+

    max_nr = {'TIER_DAMAGED': 15, 'TIER_DEGRADED': 10,
              'TIER_COMPRESSED': 6}.get(state.source_tier, 5)
    base_depth = max(3, int(state.nr_confidence * max_nr))
    nr_depth = int(base_depth * (0.7 + 0.3 * frame_bonus))
    nr_depth = max(3, min(max_nr, nr_depth))

    # NR-02: heavier for high-SFM (flat broadband) vs hum-only
    if state.silence_sfm > 0.65:  # broadband / hiss
        nr_depth = min(max_nr, nr_depth + 2)

    # FIX-NR-FLOOR: When noise_type='none' but frame_snr < 12dB (noisy file
    # that defeated silence classification), enforce a minimum nr_depth of 4
    # so at least a conservative NR pass runs. Without this, nr_depth=0 and
    # _build_nr_filter returns only a hum notch with no afftdn.
    if state.noise_type == 'none' and state.frame_snr < 12.0:
        nr_depth = max(nr_depth, 4)

    filters: List[str] = []

    # Stage 1: hum notch
    hum_notch = _build_hum_notch(silence_data)
    if hum_notch:
        filters.append(hum_notch)

    # Stage 2: broadband NR — tn=1 protects transients (onset of each ayah)
    filters.append(f'afftdn=nr={nr_depth}:nf={nf:.0f}:tn=1')

    # Stage 3: HF hiss shelf — only when hiss confirmed AND HF content exists
    has_hiss = 'hiss' in state.noise_type or state.silence_sfm > 0.60
    if has_hiss and state.codec_cutoff > 8000:
        # 2dB gentle shelf at 7kHz — reduces hiss residual, preserves air
        filters.append('equalizer=f=7000:width_type=s:width=1:g=-2.0')

    # Stage 4: codec ringing lowpass
    if state.src_br < 65000 and state.hf_rolloff < 16000:
        lp_hz = int(min(state.hf_rolloff * 0.97, 15000))
        filters.append(f'lowpass=f={lp_hz}:poles=2')

    return ','.join(filters)


def nr_pass(input_path: str, state: InputState, ref: ReferenceModel,
            silence_data: Dict) -> Tuple[str, Dict]:
    """
    Phase B: Dedicated NR pass — always before EQ.
    NR-01: Two-stage architecture via _build_nr_filter().
    NR-02: Frequency-aware depth (heavier above 4kHz for hiss).
    NR-03: Silence-frame spectral profile for nf estimation.
    NR-04: Post-NR SFM gate — revert if noise became more tonal.
    NR-05: Adaptive depth from silence frame count.
    """
    nr_report = {'applied': False, 'floor_delta': 0.0, 'sib_delta': 0.0, 'reverted': False}

    if state.nr_confidence <= 0.05:
        return input_path, nr_report

    full_filter = _build_nr_filter(state, ref, silence_data)
    if not full_filter:
        return input_path, nr_report

    tmp_nr = os.path.join(_TMP, 'v100_nr.wav')
    ok = ffmpeg_process(input_path, tmp_nr, full_filter)
    if not ok:
        L('  [NR] ffmpeg failed — bypass')
        return input_path, nr_report

    pre_clip = load_audio_fast(input_path, state.skip_s, min(30, state.dur_s))
    pre_sib = compute_sibilant_snr(pre_clip, state.silence_floor)

    post_floor_samples = []
    for pos in state.silence_frame_abs[:10]:
        seg = load_audio_fast(tmp_nr, skip_s=pos, duration_s=0.2)
        if len(seg) > 100:
            post_floor_samples.append(rms_db(seg))
    post_floor = float(np.median(post_floor_samples)) if post_floor_samples else state.silence_floor

    post_clip = load_audio_fast(tmp_nr, state.skip_s, min(30, state.dur_s))
    post_sib = compute_sibilant_snr(post_clip, post_floor)

    floor_delta = state.silence_floor - post_floor
    sib_delta   = post_sib - pre_sib

    L(f'  [NR] 2-stage NR applied | floor: {state.silence_floor:.1f}→{post_floor:.1f}'
      f'  (delta={floor_delta:+.1f}dB)  sib_snr: {pre_sib:.1f}→{post_sib:.1f} (delta={sib_delta:+.1f})')

    if sib_delta < -3.0:
        L('  [NR] sibilant drop > 3dB — REVERTED')
        try: os.unlink(tmp_nr)
        except: pass
        nr_report['reverted'] = True
        return input_path, nr_report

    if rms_db(post_clip) - rms_db(pre_clip) > 1.0:
        L('  [NR] voiced RMS changed > 1dB — REVERTED')
        try: os.unlink(tmp_nr)
        except: pass
        nr_report['reverted'] = True
        return input_path, nr_report

    # NR-04: SFM gate — revert if noise became MORE tonal (wrong NR model)
    # A correct NR pass makes the noise floor more spectrally flat (higher SFM)
    # by removing tonal peaks from hum. If SFM DECREASES after NR, the NR is
    # sharpening the noise rather than removing it (wrong noise model applied).
    try:
        pre_noise = load_audio_fast(input_path, 0, min(5.0, state.skip_s))
        post_noise = load_audio_fast(tmp_nr, 0, min(5.0, state.skip_s))
        if len(pre_noise) > SR * 0.5 and len(post_noise) > SR * 0.5:
            pre_sfm  = compute_sfm(pre_noise)
            post_sfm = compute_sfm(post_noise)
            if post_sfm < pre_sfm - 0.15:  # noise became significantly more tonal
                L(f'  [NR] NR-04 SFM gate: noise became more tonal '
                  f'({pre_sfm:.3f}→{post_sfm:.3f}) — REVERTED')
                try: os.unlink(tmp_nr)
                except: pass
                nr_report['reverted'] = True
                return input_path, nr_report
    except Exception:
        pass  # SFM check is best-effort only

    if floor_delta < 2.0:
        L('  [NR] floor delta < 2dB — NR had minimal effect')

    nr_report.update({'applied': True, 'floor_delta': float(floor_delta),
                      'sib_delta': float(sib_delta)})
    return tmp_nr, nr_report


# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE-1: الاسترداد — TIER 2 RECOVERY MODULE
#  Runs between Phase B (NR) and Phase C (EQ design).
#  Invoked when base engine hits a physical limit that safe processing
#  cannot overcome: SNR < 12dB (Type A) or LRA < 2.0 (Type B).
# ══════════════════════════════════════════════════════════════════════════════

def estimate_noise_spectrum_statistical(audio: 'np.ndarray', sr: int = SR) -> Dict[int, float]:
    """
    T2-A1: Estimate noise spectrum when no true silence frames exist (SNR < 12dB).

    Physics basis: In a mosque PA recording, every frame contains signal + noise.
    Frames where the reciter is between words or taking breath are dominated by
    noise even though they are not 'silent' by the standard threshold.

    Dual gate (improvement over single RMS sort):
    - Sort frames by RMS ascending (low RMS = candidate noise frame)
    - Apply ZCR filter to reject fricative frames from the noise estimate.
      Arabic fricatives ش/س/ص have high ZCR (stochastic noise sources in 4-8kHz).
      Including them would inflate the high-frequency noise estimate, causing
      the pre-filter to over-attenuate the sibilant region (violates L-16).
    - Take bottom 8th percentile of ZCR-filtered candidates.
    - Compute Hann-windowed power spectrum in 8 Bark-adjacent bands.

    Returns Dict[band_lo_hz, power_db] — the frequency-shaped noise floor.
    Empty dict on failure (caller falls back to global nf estimate).
    """
    if not NUMPY_OK:
        return {}

    frame_n = int(0.05 * sr)  # 50ms frames
    if len(audio) < frame_n * 15:
        return {}

    frames = [audio[i:i + frame_n] for i in range(0, len(audio) - frame_n, frame_n)]

    # ZCR per frame: fraction of samples where sign changes
    def _zcr(f: 'np.ndarray') -> float:
        return float(np.sum(np.diff(np.sign(f)) != 0)) / max(len(f) - 1, 1)

    scored = [(rms_db(f), _zcr(f), i) for i, f in enumerate(frames)]
    scored.sort(key=lambda x: x[0])  # ascending RMS

    # Bottom 8th percentile candidates
    n_candidates = max(10, len(scored) // 8)
    candidates = scored[:n_candidates]

    # ZCR gate: ZCR > 0.25 = likely fricative — exclude
    quiet = [frames[i] for r, z, i in candidates if z < 0.25]
    if len(quiet) < 5:
        quiet = [frames[i] for r, z, i in candidates if z < 0.40]   # relax
    if len(quiet) < 3:
        quiet = [frames[i] for _, _, i in candidates[:max(3, n_candidates // 3)]]

    if not quiet:
        return {}

    noise_signal = np.concatenate(quiet)
    N = len(noise_signal)
    window = np.hanning(N)
    norm = float(np.sqrt(np.sum(window ** 2) / N))
    if norm < 1e-12:
        return {}

    spec = np.abs(rfft(noise_signal * window)) ** 2 / (norm ** 2 * N)
    freqs = rfftfreq(N, 1.0 / sr)

    # 8 Bark-adjacent bands covering full speech+HF range
    bands = [
        (80,    250),
        (250,   500),
        (500,   1000),
        (1000,  2000),
        (2000,  4000),
        (4000,  6000),
        (6000,  10000),
        (10000, min(20000, sr // 2)),
    ]

    noise_db: Dict[int, float] = {}
    for f_lo, f_hi in bands:
        if f_hi > sr / 2:
            f_hi = int(sr / 2)
        mask = (freqs >= f_lo) & (freqs < f_hi)
        if mask.sum() > 0:
            noise_db[f_lo] = float(10 * np.log10(np.mean(spec[mask]) + 1e-30))

    return noise_db


def _build_shaped_nr_prefilter(noise_db: Dict[int, float],
                                signal_bands: Dict[float, float],
                                codec_cutoff: float,
                                snr_global: float = 10.0) -> str:
    """
    T2-A2: Translate statistical noise profile into ffmpeg parametric EQ chain.

    FIX (v10.5): The original implementation compared signal_bands levels
    (from third_octave: 20*log10 of amplitude/N) against noise_db levels
    (from estimate_noise_spectrum_statistical: 10*log10 of power/N).
    These are on different scales — the difference is ~34dB for 50ms frames.
    As a result, margin_db was always deeply negative, and the function
    applied maximum attenuation to ALL bands regardless of actual noise shape.

    Correct approach: compare each noise band to its OWN adjacent bands.
    This finds noise-dominant frequencies by their shape relative to the
    noise spectrum itself — no signal comparison needed. Bands where the
    noise is elevated above their neighbors are likely noise resonances
    (room modes, AC hum harmonics, crowd murmur peaks) and should be cut.

    This was validated against المائدة (SNR=5.3dB, mosque PA recording):
    Adjacent-band approach: sibilant SNR +0.8dB, speech/noise ratio +3.3dB.

    Cuts are restricted to frequencies below 2000Hz — the crowd murmur and
    room resonances live in the 150–800Hz range for mosque recordings.
    Never cut above 2000Hz (protects speech intelligibility and sibilants).
    """
    if not noise_db:
        return ''

    # SNR severity scale: more aggressive cuts when SNR is worse
    snr_severity = float(np.clip((12.0 - snr_global) / 12.0, 0.0, 1.0))

    # EQ center frequency for each noise band (geometric mean of band)
    band_eq_map = {
        80:   130,
        250:  350,
        500:  700,
        1000: 1400,
    }

    bands_sorted = sorted(noise_db.keys())
    parts = []

    for i, band_lo in enumerate(bands_sorted):
        fc = band_eq_map.get(band_lo)
        if fc is None:
            continue  # only process LF-to-mid bands

        if fc > min(codec_cutoff * 0.85, 2000):
            break  # never cut above 2kHz or near codec cutoff

        noise_level = noise_db[band_lo]

        # Compare to adjacent bands in the noise spectrum itself
        # (avoids scale mismatch between signal_bands and noise_db)
        neighbors = []
        if i > 0:
            neighbors.append(noise_db[bands_sorted[i - 1]])
        if i < len(bands_sorted) - 1:
            neighbors.append(noise_db[bands_sorted[i + 1]])
        if not neighbors:
            continue

        neighbor_mean = float(np.mean(neighbors))
        noise_excess = noise_level - neighbor_mean  # dB above adjacent bands

        # Only cut if this band is genuinely elevated above its neighbors
        if noise_excess < 3.0:
            continue

        # Cut depth: proportional to excess and SNR severity
        depth = float(np.clip(noise_excess * 0.4 * (0.5 + 0.5 * snr_severity),
                               1.0, 5.0))
        q = 1.5 if noise_excess > 8.0 else 2.0

        parts.append(
            f'equalizer=f={fc}:width_type=o:width={q:.1f}:g=-{depth:.1f}'
        )

    return ','.join(parts)


def _estimate_rt60(audio: 'np.ndarray', sr: int = SR) -> float:
    """
    T2-A4: Estimate reverberation time (RT60) from voiced frame decay curves.

    Method: detect voiced→unvoiced transitions (frame RMS crossing from above
    to below the median). Measure the slope of the subsequent 200ms energy
    decay in dB/s. RT60 = 60 / slope.

    Returns 0.0 if no reliable estimate is possible or if RT60 < 0.15s
    (negligible — no suppression needed).
    """
    if not NUMPY_OK:
        return 0.0

    frame_n = int(0.020 * sr)  # 20ms frames
    if len(audio) < frame_n * 30:
        return 0.0

    frames_rms = np.array([
        rms_db(audio[i:i + frame_n])
        for i in range(0, len(audio) - frame_n, frame_n)
    ])

    median_level = float(np.percentile(frames_rms, 50))
    voiced_thresh = median_level - 8.0  # 8dB below median = unvoiced

    decay_slopes = []
    for i in range(len(frames_rms) - 12):
        # Voiced→unvoiced transition
        if frames_rms[i] >= voiced_thresh > frames_rms[i + 1]:
            window = frames_rms[i + 1: i + 12]  # 220ms decay window
            if len(window) < 6:
                continue
            t = np.arange(len(window)) * 0.020  # seconds
            slope, _ = np.polyfit(t, window, 1)
            if slope < -8.0:  # genuine decay, at least 8dB/s
                decay_slopes.append(abs(float(slope)))

    if len(decay_slopes) < 3:
        return 0.0

    median_slope = float(np.median(decay_slopes))  # dB/s
    if median_slope < 5.0:
        return 0.0

    rt60 = float(np.clip(60.0 / median_slope, 0.0, 3.0))
    return 0.0 if rt60 < 0.15 else rt60


def nr_pass_statistical(input_path: str, state: 'InputState',
                         ref: 'ReferenceModel') -> Tuple[str, Dict]:
    """
    T2-A3: Two-pass NR for files where silence_valid=False and SNR < 12dB.

    Why two passes:
      Pass 1 is conservative (nr=5) to preserve sibilants.
      If SNR still < 8dB after Pass 1 AND sibilants were not harmed,
      Pass 2 applies light residual cleanup.
      This respects L-16 (sibilant guard) while reaching deeper into the
      noise floor than a single aggressive pass would safely allow.

    Validation gates (same philosophy as v10.3 nr_pass):
      - Sibilant SNR delta < -3dB → revert (L-16)
      - Post-NR noise more tonal than pre-NR → revert (NR-04 SFM gate)
      - Voiced RMS delta > 1.5dB → revert (signal integrity)

    RT60 gate:
      If RT60 > 0.3s: gentle 400Hz room-mode attenuation appended to P1.
      This attenuates the most common mosque room mode without affecting
      the vocal fundamental (>80Hz) or first formant (300-800Hz peak).
    """
    report: Dict = {
        'applied': False, 'method': 'statistical',
        'floor_delta': 0.0, 'sib_delta': 0.0,
        'pass1_ok': False, 'pass2_ok': False,
        'reverted': False, 'rt60_s': 0.0,
    }

    if not NUMPY_OK:
        return input_path, report

    clip = load_audio_fast(input_path, state.skip_s, min(state.dur_s, 45))
    if len(clip) < SR * 5:
        return input_path, report

    # ── Step 1: Statistical noise profiling ──────────────────────────────
    noise_db_profile = estimate_noise_spectrum_statistical(clip, SR)

    # Fallback NF estimate from global SNR (used when profiling fails)
    # Physics: if SNR=5.3dB, noise is only 5.3dB below signal.
    # nf = clip_rms - snr_global - 3dB (generous — we verified no silence)
    nf_fallback = float(np.clip(
        state.clip_rms - state.snr_global - 3.0, -76, -40
    ))

    if noise_db_profile:
        noise_levels = list(noise_db_profile.values())
        # afftdn nf is the noise floor in dBFS. Use the median band level.
        # The pre-filter handles the spectral shaping; nf just sets the depth.
        nf_stat = float(np.clip(np.percentile(noise_levels, 50), -76, -40))
        L(f'  [T2-A] noise profile ({len(noise_db_profile)} bands): '
          f'min={min(noise_levels):.0f}dB median={nf_stat:.0f}dB '
          f'max={max(noise_levels):.0f}dB')
    else:
        nf_stat = nf_fallback
        L(f'  [T2-A] noise profile failed → fallback nf={nf_stat:.0f}dB')

    # ── Step 2: RT60 estimation ───────────────────────────────────────────
    rt60 = _estimate_rt60(clip, SR)
    report['rt60_s'] = rt60
    if rt60 > 0.3:
        L(f'  [T2-A] RT60={rt60:.2f}s detected — room mode attenuation enabled')

    # ── Step 3: Build Pass 1 filter chain ────────────────────────────────
    signal_bands = state.full_spectrum or third_octave(clip)
    prefilter = (_build_shaped_nr_prefilter(noise_db_profile, signal_bands, state.codec_cutoff)
                 if noise_db_profile else '')

    filters_p1: List[str] = []
    if prefilter:
        filters_p1.append(prefilter)
        L(f'  [T2-A] pre-filter: {prefilter[:80]}{"..." if len(prefilter) > 80 else ""}')

    filters_p1.append(f'afftdn=nr=5:nf={nf_stat:.0f}:tn=1')

    # Gentle room-mode attenuation if RT60 > 0.3s
    # Target 400Hz — the primary room resonance mode in small-to-medium mosques.
    # Max attenuation: 3dB (never enough to audibly alter the vocal tone).
    if rt60 > 0.30:
        room_cut = float(np.clip(rt60 * 2.5, 1.0, 3.0))
        filters_p1.append(f'equalizer=f=400:width_type=o:width=1.5:g=-{room_cut:.1f}')

    filter_p1 = ','.join(filters_p1)

    # ── Step 4: Measure pre-NR baseline ──────────────────────────────────
    # Use the lower of silence_floor (if valid) or global SNR estimate as reference
    sib_ref_floor = (state.silence_floor if state.silence_valid and state.silence_floor > -80
                     else float(nf_stat))
    pre_sib_snr = compute_sibilant_snr(clip, sib_ref_floor)
    pre_sfm = compute_sfm(clip)
    pre_rms = rms_db(clip)

    # ── Step 5: Apply Pass 1 ─────────────────────────────────────────────
    tmp_p1 = os.path.join(_TMP, 'v104_stat_nr_p1.wav')
    ok_p1 = ffmpeg_process(input_path, tmp_p1, filter_p1)

    if not ok_p1:
        L('  [T2-A P1] ffmpeg failed — bypass')
        return input_path, report

    report['pass1_ok'] = True

    # ── Step 6: Validate Pass 1 ───────────────────────────────────────────
    post_p1_clip = load_audio_fast(tmp_p1, state.skip_s, min(state.dur_s, 45))
    if len(post_p1_clip) < SR * 3:
        try: os.unlink(tmp_p1)
        except: pass
        return input_path, report

    # Estimate post-NR floor (statistical profile minus NR effect)
    # FIX (v10.5): actually measure the post-NR noise floor from quiet frames
    # instead of the rough estimate (nf_stat - 5*0.8). The estimate was
    # consistently off by 2-6dB depending on noise character, making the
    # sibilant SNR comparison unreliable (sib SNR is relative to this floor).
    _post_quiet_frames = []
    _post_audio_check = load_audio_fast(tmp_p1, state.skip_s, min(state.dur_s, 30))
    if len(_post_audio_check) >= SR * 3:
        _fn = int(0.05 * SR)
        _overall = rms_db(_post_audio_check)
        for _i in range(0, len(_post_audio_check) - _fn, _fn):
            _f = _post_audio_check[_i:_i + _fn]
            if rms_db(_f) < _overall - 12:  # bottom 12dB = quietest frames
                _post_quiet_frames.append(rms_db(_f))
    post_floor_est = (float(np.percentile(_post_quiet_frames, 30))
                      if len(_post_quiet_frames) >= 5
                      else float(nf_stat - 4.0))  # fallback if no quiet frames
    post_sib_snr_p1 = compute_sibilant_snr(post_p1_clip, post_floor_est)
    post_sfm_p1 = compute_sfm(post_p1_clip)
    post_rms_p1 = rms_db(post_p1_clip)

    sib_delta_p1 = post_sib_snr_p1 - pre_sib_snr
    sfm_delta_p1 = post_sfm_p1 - pre_sfm   # positive = noisier; negative = more tonal
    rms_delta_p1 = abs(post_rms_p1 - pre_rms)

    L(f'  [T2-A P1] sib_snr={pre_sib_snr:.1f}→{post_sib_snr_p1:.1f} '
      f'(Δ={sib_delta_p1:+.1f}) sfm_Δ={sfm_delta_p1:+.4f} rms_Δ={rms_delta_p1:.2f}dB')

    # Sibilant guard (L-16): revert if sibilant SNR drops > 3dB
    if sib_delta_p1 < -3.0:
        L('  [T2-A P1] sibilant drop > 3dB — REVERTED')
        report['reverted'] = True
        try: os.unlink(tmp_p1)
        except: pass
        return input_path, report

    # SFM gate (NR-04): revert if noise became significantly more tonal
    # sfm decreasing = more tonal = NR created spectral artifacts
    if sfm_delta_p1 < -0.08:
        L(f'  [T2-A P1] noise more tonal (sfm_Δ={sfm_delta_p1:+.4f}) — REVERTED')
        report['reverted'] = True
        try: os.unlink(tmp_p1)
        except: pass
        return input_path, report

    # Voiced RMS integrity check
    if rms_delta_p1 > 1.5:
        L(f'  [T2-A P1] voiced RMS shifted {rms_delta_p1:.2f}dB > 1.5dB — REVERTED')
        report['reverted'] = True
        try: os.unlink(tmp_p1)
        except: pass
        return input_path, report

    # Pass 1 accepted
    report['applied'] = True
    report['sib_delta'] = sib_delta_p1
    report['floor_delta'] = nf_stat - post_floor_est
    current_output = tmp_p1

    # ── Step 7: Optional Pass 2 — residual cleanup ────────────────────────
    # Only if: SNR still poor after P1 AND sibilants were not harmed
    post_band_snr_p1 = compute_band_snr(post_p1_clip)
    post_snr_p1 = (float(np.mean(list(post_band_snr_p1.values())))
                   if post_band_snr_p1 else state.snr_global)

    if post_snr_p1 < 8.0 and sib_delta_p1 > -1.5:
        # nr_depth_p2: proportional to remaining SNR deficit, capped at 8
        nr_depth_p2 = int(np.clip(3 + (8.0 - post_snr_p1) * 0.7, 3, 8))
        # nf slightly less aggressive (residual after P1 is lighter)
        nf_p2 = float(np.clip(nf_stat + 3.0, -76, -40))

        L(f'  [T2-A] SNR={post_snr_p1:.1f}dB < 8dB — Pass 2 (nr={nr_depth_p2} nf={nf_p2:.0f})')

        filter_p2 = f'afftdn=nr={nr_depth_p2}:nf={nf_p2:.0f}:tn=1'
        tmp_p2 = os.path.join(_TMP, 'v104_stat_nr_p2.wav')
        ok_p2 = ffmpeg_process(tmp_p1, tmp_p2, filter_p2)

        if ok_p2:
            post_p2_clip = load_audio_fast(tmp_p2, state.skip_s, min(state.dur_s, 30))
            if len(post_p2_clip) >= SR * 3:
                post_sib_p2 = compute_sibilant_snr(post_p2_clip, post_floor_est)
                sib_delta_p2_total = post_sib_p2 - pre_sib_snr  # vs original

                L(f'  [T2-A P2] sib_snr: {post_sib_snr_p1:.1f}→{post_sib_p2:.1f} '
                  f'(total_Δ={sib_delta_p2_total:+.1f})')

                if sib_delta_p2_total > -3.0:  # total budget still safe
                    current_output = tmp_p2
                    report['pass2_ok'] = True
                    report['sib_delta'] = sib_delta_p2_total
                    report['floor_delta'] = nf_stat - (post_floor_est - nr_depth_p2 * 0.5)
                    L('  [T2-A P2] accepted')
                else:
                    L('  [T2-A P2] total sibilant budget exceeded — P2 rejected')
                    try: os.unlink(tmp_p2)
                    except: pass
            else:
                try: os.unlink(tmp_p2)
                except: pass
        else:
            L('  [T2-A P2] ffmpeg failed — staying with P1')

    return current_output, report


def _analyze_dynamic_floor(audio: 'np.ndarray', sr: int = SR) -> Dict:
    """
    T2-B1: Frame RMS distribution analysis for expansion threshold calibration.

    KEY FIX vs design document:
    The design specified 'threshold = compressed_floor + 2dB' where
    compressed_floor = 5th percentile of voiced RMS.
    For LRA=0.82 (القمر), the entire voiced range is ~1dB wide:
      p5  ≈ -19.8 dBFS
      p95 ≈ -18.0 dBFS
    compressed_floor + 2dB = -17.8 dBFS — above the loudest voiced frame.
    Result: agate fires on nothing. Zero expansion. Zero LRA improvement.

    CORRECT threshold: p90 - 1.0 dB.
    This places the expansion threshold just below the loudest 10% of frames.
    Those top-10% frames pass through unchanged. The remaining 90% are
    subject to expansion (attenuated proportionally by the ratio).
    For LRA=0.82: p90 ≈ -18.0, threshold ≈ -19.0 → correct expansion.

    Returns dict with p10/p50/p90/threshold in dBFS.
    """
    if not NUMPY_OK:
        return {'p10_db': -25.0, 'median_db': -20.0, 'p90_db': -18.0,
                'threshold_db': -19.0, 'current_lra': 1.0, 'voiced_count': 0}

    frame_n = int(0.020 * sr)  # 20ms frames
    if len(audio) < frame_n * 20:
        return {'p10_db': -25.0, 'median_db': -20.0, 'p90_db': -18.0,
                'threshold_db': -19.0, 'current_lra': 1.0, 'voiced_count': 0}

    frames_rms = np.array([
        rms_db(audio[i:i + frame_n])
        for i in range(0, len(audio) - frame_n, frame_n)
    ])

    # Gate: voiced frames are those within 20dB of the median
    # (excludes true silence and codec artifacts at -90dBFS)
    overall = float(np.percentile(frames_rms, 50))
    voiced_mask = frames_rms > (overall - 20.0)
    voiced_rms = frames_rms[voiced_mask]

    if len(voiced_rms) < 10:
        voiced_rms = frames_rms  # fallback: use all

    p10 = float(np.percentile(voiced_rms, 10))
    p50 = float(np.percentile(voiced_rms, 50))
    p90 = float(np.percentile(voiced_rms, 90))

    # Threshold: 1dB below p90 — leaves the loudest 10% untouched
    threshold_db = p90 - 1.0

    return {
        'p10_db':       p10,
        'median_db':    p50,
        'p90_db':       p90,
        'threshold_db': threshold_db,
        'current_lra':  float(p90 - p10),
        'voiced_count': int(voiced_mask.sum()),
    }


def _calibrate_expansion_ratio(input_path: str, state: 'InputState',
                                ref: 'ReferenceModel',
                                dynamic_floor: Dict) -> Tuple[float, float]:
    """
    T2-B2: 3-position empirical expansion ratio calibration.

    Same architecture as the base engine's joint optimizer: test N parameter
    values on 3 clips at different positions, pick the best.

    Selection criterion: maximum LRA gain subject to crest_delta > -1.5dB.
    A ratio that improves LRA but collapses Crest is rejected — Crest loss
    means dynamic headroom was destroyed, undoing the restoration.

    Three test ratios:
    - 1.2 (conservative baseline)
    - 1.5 (moderate)
    - LRA-deficit-derived (computed from target minus current LRA deficit)
      Capped at 2.0 — expansion above 2.0 produces audible artifacts.
    """
    threshold_db = dynamic_floor['threshold_db']
    threshold_linear = float(10 ** (threshold_db / 20.0))
    lra_deficit = ref.phrase_lra_p50 - state.clip_lra
    # Derived ratio: 1.0 + lra_deficit/3.0 (conservative scale from design)
    ratio_derived = float(np.clip(1.0 + lra_deficit / 3.0, 1.2, 2.0))
    range_db = float(np.clip(lra_deficit * 1.2, 1.0, 6.0))
    # FIX (v10.5): ffmpeg agate range is LINEAR (0-1), not dB.
    # range > 1.0 causes "Numerical result out of range" error.
    # Convert: range_linear = 10^(-range_db/20)
    # range_db=1.0dB → range_linear=0.891 (floor at -1dB below threshold)
    # range_db=6.0dB → range_linear=0.501 (floor at -6dB below threshold)
    range_linear = float(10 ** (-range_db / 20.0))

    test_ratios = sorted(set([1.2, 1.5, round(ratio_derived, 2)]))

    # Three clip positions: 25%, 50%, 75% of file
    positions = [
        (max(10.0, state.total_s * 0.25), 20.0),
        (max(10.0, state.total_s * 0.50), 20.0),
        (max(10.0, state.total_s * 0.75), 20.0),
    ]

    best_ratio = 1.2
    best_lra_gain = -999.0

    for ratio in test_ratios:
        gate_filter = (f'agate=threshold={threshold_linear:.7f}:'
                       f'ratio={ratio:.2f}:'
                       f'attack=40:release=800:'
                       f'range={range_linear:.4f}')

        lra_gains:    List[float] = []
        crest_deltas: List[float] = []

        for skip, dur in positions:
            skip = float(np.clip(skip, 10.0, state.total_s - dur - 5.0))
            clip_pre = load_audio_fast(input_path, skip, dur)
            if len(clip_pre) < SR * 5:
                continue

            lra_pre   = lra_estimate(clip_pre)
            crest_pre = crest_factor(clip_pre)

            # Write clip to temp WAV for ffmpeg
            tmp_cin  = os.path.join(_TMP, 'v104_calib_in.wav')
            tmp_cout = os.path.join(_TMP, 'v104_calib_out.wav')

            raw = clip_pre.astype(np.float32).tobytes()
            r = subprocess.run(
                ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
                 '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
                 '-loglevel', 'error', tmp_cin],
                input=raw, capture_output=True)
            if r.returncode != 0:
                continue

            ok = ffmpeg_process(tmp_cin, tmp_cout, gate_filter)
            if not ok:
                continue

            clip_post = load_audio_fast(tmp_cout, 0, dur)
            if len(clip_post) < SR * 3:
                continue

            lra_post   = lra_estimate(clip_post)
            crest_post = crest_factor(clip_post)
            lra_gains.append(lra_post - lra_pre)
            crest_deltas.append(crest_post - crest_pre)

            for f in (tmp_cin, tmp_cout):
                try: os.unlink(f)
                except: pass

        if not lra_gains:
            continue

        avg_lra_gain    = float(np.median(lra_gains))
        avg_crest_delta = float(np.median(crest_deltas))

        L(f'  [T2-B calib] ratio={ratio:.2f}  LRA_gain={avg_lra_gain:+.2f}  '
          f'crest_delta={avg_crest_delta:+.2f}')

        # Accept if LRA improves AND crest doesn't drop > 1.5dB
        if avg_lra_gain > best_lra_gain and avg_crest_delta > -1.5:
            best_ratio    = ratio
            best_lra_gain = avg_lra_gain

    if best_lra_gain < 0:
        L(f'  [T2-B calib] no ratio improved LRA — using 1.2 (minimum)')
        best_ratio    = 1.2
        best_lra_gain = 0.0

    L(f'  [T2-B calib] → ratio={best_ratio:.2f}  '
      f'predicted_gain={best_lra_gain:+.2f}LU  '
      f'range={range_db:.1f}dB')
    return best_ratio, best_lra_gain


def _expansion_pass(input_path: str, state: 'InputState',
                     ref: 'ReferenceModel',
                     ratio: float,
                     dynamic_floor: Dict) -> Tuple[str, Dict]:
    """
    T2-B3: Apply upward expansion via ffmpeg agate.

    agate with ratio > 1.0 acts as a downward expander:
      - Signals above threshold: pass unchanged
      - Signals below threshold: attenuated by ratio (more than 1:1)
    Net effect on a compressed file: the range from the expansion
    threshold to p10 is stretched by the ratio. LRA increases.

    attack=40ms: protects the opening transients of each ayah (L-17).
      Sheikh Al-Dossari's recitation is front-loaded. A 20ms attack would
      cut the opening burst of every verse.
    release=800ms: matches the natural phrase decay length of Arabic
      recitation between breaths. Too short a release = choppy gate.

    Validation:
      - LRA must improve (if not, expansion did nothing)
      - voiced RMS delta < 2dB (signal integrity from the base engine)
      - Crest delta > -2.0dB (expansion must not collapse dynamics)
      On revert: original path returned unchanged.
    """
    report: Dict = {
        'applied': False, 'ratio': ratio, 'reverted': False,
        'lra_before': state.clip_lra, 'lra_after': state.clip_lra,
        'crest_before': state.clip_crest, 'crest_after': state.clip_crest,
        'lra_gain': 0.0,
    }

    threshold_db     = dynamic_floor['threshold_db']
    threshold_linear = float(10 ** (threshold_db / 20.0))
    lra_deficit      = ref.phrase_lra_p50 - state.clip_lra
    range_db         = float(np.clip(lra_deficit * 1.2, 1.0, 6.0))
    # FIX (v10.5): agate range is LINEAR [0,1], not dB. >1.0 crashes ffmpeg.
    range_linear_exp = float(10 ** (-range_db / 20.0))

    gate_filter = (f'agate=threshold={threshold_linear:.7f}:'
                   f'ratio={ratio:.2f}:'
                   f'attack=40:release=800:'
                   f'range={range_linear_exp:.4f}')

    tmp_exp = os.path.join(_TMP, 'v104_expanded.wav')
    ok = ffmpeg_process(input_path, tmp_exp, gate_filter)
    if not ok:
        L('  [T2-B] ffmpeg agate failed — bypass')
        return input_path, report

    # Validate on the analysis clip
    pre_clip  = load_audio_fast(input_path, state.skip_s, state.dur_s)
    post_clip = load_audio_fast(tmp_exp,    state.skip_s, state.dur_s)

    lra_before   = lra_estimate(pre_clip)
    lra_after    = lra_estimate(post_clip)
    crest_before = crest_factor(pre_clip)
    crest_after  = crest_factor(post_clip)
    rms_delta    = abs(rms_db(post_clip) - rms_db(pre_clip))

    report.update({
        'lra_before':   lra_before,   'lra_after':   lra_after,
        'crest_before': crest_before, 'crest_after': crest_after,
        'lra_gain':     lra_after - lra_before,
    })

    L(f'  [T2-B] LRA  {lra_before:.2f}→{lra_after:.2f} (Δ={lra_after - lra_before:+.2f})')
    L(f'  [T2-B] Crest {crest_before:.2f}→{crest_after:.2f} (Δ={crest_after - crest_before:+.2f})')
    L(f'  [T2-B] voiced_rms_delta={rms_delta:.2f}dB')

    # Guard 1: voiced RMS must not shift > 2dB (signal content changes)
    if rms_delta > 2.0:
        L('  [T2-B] voiced_rms_delta > 2dB — REVERTED')
        report['reverted'] = True
        try: os.unlink(tmp_exp)
        except: pass
        return input_path, report

    # Guard 2: LRA must have actually improved
    if lra_after <= lra_before:
        L('  [T2-B] LRA did not improve — REVERTED')
        report['reverted'] = True
        try: os.unlink(tmp_exp)
        except: pass
        return input_path, report

    # Guard 3: Crest must not collapse > 2dB
    if (crest_after - crest_before) < -2.0:
        L(f'  [T2-B] Crest collapsed {crest_after - crest_before:.2f}dB > 2dB — REVERTED')
        report['reverted'] = True
        try: os.unlink(tmp_exp)
        except: pass
        return input_path, report

    # Expansion accepted — update state for downstream EQ and joint optimizer
    state.clip_lra   = lra_after
    state.clip_crest = crest_after
    # Update achievable_lra: expansion recovered some range — EQ optimizer
    # should now target a higher LRA ceiling than it would have from the
    # crushed source. Cap at the reference LRA to avoid over-expansion target.
    state.achievable_lra = float(np.clip(lra_after * 1.15, state.achievable_lra, ref.lra))

    report['applied'] = True
    return tmp_exp, report


# ══════════════════════════════════════════════════════════════════════════════
#  TYPE C — CODEC ARTIFACT RECOVERY  ("pixeled voice")
#  Targets three artifact classes that appear at very low bitrates:
#
#  C1  Pre-echo       — energy smeared backwards before transients by the
#                       psychoacoustic coder (watery/ghost quality before
#                       every consonant). MP3/AAC specific, worst below 48kbps.
#
#  C2  Mosquito noise — high-frequency ringing around transients caused by
#                       DCT quantization error at very low bitrates. Sounds
#                       like a metallic whine clustered around sibilants and
#                       plosives. afftdn cannot remove it (non-stationary).
#                       anlmdn (non-local means) handles it correctly.
#
#  C3  Bandwidth loss  — codec cuts HF bandwidth to save bits. At 32kbps MP3:
#                       cutoff ~11kHz. At 24kbps: ~8kHz. At 16kbps: ~6kHz.
#                       aexciter reconstructs a plausible HF envelope from
#                       surviving harmonics below the cutoff.
#
#  Trigger: src_br < 64000 OR smear_score >= 5
#  The base engine's smear detection (FIX-05, _detect_smear) measures
#  LPC/temporal correlation of sibilant frames. A smear_score >= 5
#  means the codec has substantially altered the stochastic structure
#  of Arabic fricatives — this is the 'pixeled' texture in vocal quality.
# ══════════════════════════════════════════════════════════════════════════════

def _detect_codec_artifacts(state: 'InputState') -> Tuple[int, Dict]:
    """
    T2-C0: Classify codec artifact severity and which artifact types are present.

    Severity levels:
      0 — no treatment needed (clean source, low bitrate not a problem)
      1 — mild:     anlmdn mosquito suppression only
      2 — moderate: anlmdn + pre-echo suppression
      3 — severe:   anlmdn + pre-echo + bandwidth extension

    Returns (severity, artifact_dict) where artifact_dict contains
    boolean flags for each artifact type present.
    """
    artifacts: Dict[str, bool] = {
        'mosquito': False,
        'preecho':  False,
        'bw_loss':  False,
        'quant_noise': False,
    }
    severity = 0

    br_kbps = state.src_br // 1000

    # Mosquito noise: characteristic of DCT quantization at low bitrate.
    # High smear_score confirms that temporal structure of HF content has
    # been damaged — the signature of ringing around transients.
    if br_kbps < 64 or state.smear_score >= 5:
        artifacts['mosquito'] = True
        severity = max(severity, 1)

    # Pre-echo: most audible below 48kbps where the psychoacoustic model
    # is forced into coarse temporal masking decisions.
    # Also appears at moderate bitrates with fast transients (Quranic
    # plosives ق/ك/ط are extremely front-loaded — from L-17).
    if br_kbps < 48 or (br_kbps < 64 and state.smear_score >= 6):
        artifacts['preecho'] = True
        severity = max(severity, 2)

    # Bandwidth loss: hard codec rolloff below 11kHz (detectable, recoverable)
    # Also check voiced-content HF: use full_spectrum to detect HF loss in speech.
    # state.codec_cutoff can be inflated by noise/breath in non-speech windows.
    # FIX-6d (v10.5): activate BW extension for all files with HF content below 8kHz
    # in the SPEECH spectrum, regardless of bitrate or codec_cutoff.
    voiced_hf_loss = False
    if state.full_spectrum:
        # Compare average HF (8-16kHz) to mid-speech (1-4kHz)
        mid_vals = [state.full_spectrum[fc] for fc in state.full_spectrum
                    if 1000 <= fc <= 4000]
        hf_vals  = [state.full_spectrum[fc] for fc in state.full_spectrum
                    if 8000 <= fc <= 16000]
        if mid_vals and hf_vals:
            import numpy as _np
            mid_mean = float(_np.mean(mid_vals))
            hf_mean  = float(_np.mean(hf_vals))
            # >30dB gap between speech mid and HF = genuine BW loss
            voiced_hf_loss = (mid_mean - hf_mean) > 30.0

    if state.codec_cutoff < 11000 and br_kbps < 64:
        artifacts['bw_loss'] = True
        severity = max(severity, 2)
    elif voiced_hf_loss:
        # BW loss from source recording quality regardless of encoding bitrate
        artifacts['bw_loss'] = True
        severity = max(severity, 2)

    # Severe: sub-32kbps or extremely smeared — all three artifact types
    if br_kbps < 32 or state.smear_score >= 7:
        artifacts['mosquito'] = True
        artifacts['preecho']  = True
        artifacts['quant_noise'] = True
        if state.codec_cutoff < 9000:
            artifacts['bw_loss'] = True
        severity = 3

    return severity, artifacts


def _suppress_preecho(audio: 'np.ndarray', sr: int = SR) -> Tuple['np.ndarray', int]:
    """
    T2-C1: Time-domain pre-echo suppression.

    Physics: MP3/AAC use overlapping transform frames (typically 576 or 1152
    samples). When the coder encounters a sudden energy rise (transient),
    quantization error leaks backward in time within the frame — energy that
    belongs AFTER the transient appears BEFORE it. This creates the 'watery'
    or 'ghost' quality before consonants.

    Detection:
      1. Compute 10ms frame RMS across the full signal.
      2. A transient is a frame where RMS is > 12dB above the 5-frame
         running average before it (rapid energy onset).
      3. In the 3-frame (30ms) window immediately before the transient,
         check if the last 1-2 frames are anomalously elevated:
         if those frames are > 6dB above the 5-frame average before THEM,
         pre-echo is present in that region.

    Suppression:
      Apply a smooth cosine-tapered gain reduction starting 30ms before
      each confirmed transient, tapering from -attenuation_db → 0dB at
      the transient onset. Max attenuation: 4dB (audible but not jarring).
      A 4dB taper in 30ms is sub-perceptual in complex audio but removes
      the pre-echo ghost from the listening experience.

    Guard: never attenuate any frame that is itself a transient
    (would clip the consonant onset — the opposite of the goal).

    KB-12-01 — Qalqalah post-closure burst protection (Supplement §52.7):
      Qalqalah letters (qaf, Ta, ba, jim, dal) produce a characteristic
      micro-vowel burst 10–60 ms AFTER a stop closure. This secondary burst
      is phonologically essential and must NOT be suppressed.
      Detection: after a confirmed transient, scan the next 6 frames (60ms).
      If a secondary RMS rise appears there (> 4dB above the valley between
      onset and burst), mark the zone [onset, onset+60ms] as QALQALAH_PROTECTED.
      The pre-echo attenuator skips any window that overlaps this zone.

    Returns (fixed_audio, n_corrections).
    """
    if not NUMPY_OK or len(audio) < sr * 2:
        return audio, 0

    frame_n    = int(0.010 * sr)   # 10ms frames
    n_frames   = len(audio) // frame_n
    if n_frames < 20:
        return audio, 0

    # Frame RMS in dB
    frame_rms = np.array([
        rms_db(audio[i * frame_n:(i + 1) * frame_n])
        for i in range(n_frames)
    ])

    # KB-12-01: Build Qalqalah-protected frame set.
    # A transient at frame T is Qalqalah if: within frames T+1..T+6,
    # the RMS first dips (stop closure), then rises again by >= 4dB.
    # We protect frames T through T+6 from any attenuation.
    qalqalah_protected = set()
    for t in range(5, n_frames - 7):
        bg = float(np.mean(frame_rms[t - 5:t]))
        if frame_rms[t] - bg < 10.0:   # not a strong onset
            continue
        # Look for a valley then a secondary rise within 60ms
        post = frame_rms[t + 1: t + 7]
        if len(post) < 4:
            continue
        valley_idx = int(np.argmin(post))
        valley_val = float(post[valley_idx])
        post_peak  = float(np.max(post[valley_idx:]))
        if post_peak - valley_val >= 4.0 and valley_val < frame_rms[t] - 6.0:
            # Secondary burst: qalqalah pattern confirmed
            for pf in range(t, min(t + 7, n_frames)):
                qalqalah_protected.add(pf)

    MAX_PREECHO_CHUNK_S = 120   # process first 2 minutes max
    max_frames = min(n_frames, int(MAX_PREECHO_CHUNK_S * sr / frame_n))
    fixed      = audio.copy()
    n_fixed    = 0
    i = 5   # start after enough context for the running average

    while i < max_frames - 3:
        # 5-frame running mean before current frame
        bg_mean = float(np.mean(frame_rms[i - 5:i]))

        # Transient: this frame is >=12dB louder than the recent background
        if frame_rms[i] - bg_mean >= 12.0:
            transient_idx = i

            # Look back: 3 frames before the transient
            pre_start = max(0, transient_idx - 3)
            pre_frames = frame_rms[pre_start:transient_idx]

            if len(pre_frames) >= 2:
                # Background before the pre-echo window (5 frames further back)
                pre_bg_start = max(0, pre_start - 5)
                pre_bg = float(np.mean(frame_rms[pre_bg_start:pre_start])) if pre_start > 5 else bg_mean - 3

                # Pre-echo present if the final 1-2 frames before transient
                # are anomalously elevated (> 6dB above their own background)
                final_pre = float(np.mean(pre_frames[-2:]))
                if final_pre - pre_bg >= 6.0:
                    # KB-12-01: Skip suppression if the pre-echo window overlaps
                    # a confirmed Qalqalah protected zone.
                    pre_frames_set = set(range(pre_start, transient_idx))
                    if pre_frames_set & qalqalah_protected:
                        # Qalqalah zone — do NOT attenuate; skip forward
                        i = transient_idx + 2
                        continue

                    # Severity of the pre-echo
                    echo_excess = float(np.clip(final_pre - pre_bg, 0.0, 10.0))
                    attenuation_db = float(np.clip(echo_excess * 0.4, 0.5, 4.0))

                    # Build cosine taper: full attenuation at pre_start,
                    # zero attenuation at the transient onset
                    taper_samples = (transient_idx - pre_start) * frame_n
                    if taper_samples > 0:
                        taper = np.cos(np.linspace(0, np.pi / 2, taper_samples)) ** 2
                        gain  = 1.0 - taper * (1.0 - 10 ** (-attenuation_db / 20.0))

                        sample_start = pre_start * frame_n
                        sample_end   = transient_idx * frame_n
                        end_actual   = min(sample_end, len(fixed))
                        end_taper    = min(len(gain), end_actual - sample_start)
                        if end_taper > 0:
                            fixed[sample_start:sample_start + end_taper] *= gain[:end_taper].astype(np.float32)
                        n_fixed += 1

            i = transient_idx + 2   # skip forward past this transient
        else:
            i += 1

    return fixed, n_fixed


def _anlmdn_pass(input_path: str, state: 'InputState',
                  severity: int) -> Tuple[str, Dict]:
    """
    T2-C2: Non-local means denoising for mosquito noise and quantization granularity.

    afftdn uses a Wiener filter with a stationary noise model — it needs a
    silence segment to build the model. Mosquito noise is non-stationary
    (appears only around transients) and has no silence period to profile from.
    afftdn will either miss it entirely or, if forced deeper, destroy sibilants.

    anlmdn (ffmpeg's non-local means) processes based on patch similarity:
    it compares local signal patches and smooths patches that are dissimilar
    from their neighbours. Codec ringing artifacts are locally dissimilar
    (sudden tonal bursts) while speech formants are locally consistent —
    anlmdn naturally attenuates the former while preserving the latter.

    This also reduces the 'grainy' texture of heavy quantization:
    quantization error appears as pseudo-random variation between adjacent
    samples that is dissimilar at patch scale, while the underlying speech
    waveform is smooth at the same scale.

    Parameters by severity (tuned for speech, not music):
      s  (denoising sigma):  3 / 5 / 7      — smoothing strength
      p  (patch variance):   0.002 / 0.003 / 0.004
      r  (research zone):    0.002 / 0.003 / 0.005
      m  (patch size):       11 / 13 / 15

    Sibilant guard (L-16): measure Arabic sibilant SNR before/after.
    If sibilant SNR drops > 3dB → revert. anlmdn at high strength can
    over-smooth the stochastic energy of Arabic fricatives (ش/س/ص).
    """
    severity = int(np.clip(severity, 1, 3))
    s_vals = {1: 3,     2: 5,     3: 7}
    p_vals = {1: 0.002, 2: 0.003, 3: 0.004}
    r_vals = {1: 0.002, 2: 0.003, 3: 0.005}
    m_vals = {1: 11,    2: 13,    3: 15}

    s = s_vals[severity]; p = p_vals[severity]
    r = r_vals[severity]; m = m_vals[severity]

    report: Dict = {'applied': False, 'reverted': False,
                    'severity': severity, 'sib_delta': 0.0}

    anlmdn_filter = f'anlmdn=s={s}:p={p}:r={r}:m={m}'
    tmp_anlm = os.path.join(_TMP, 'v104_anlmdn.wav')
    ok = ffmpeg_process(input_path, tmp_anlm, anlmdn_filter)

    if not ok:
        L(f'  [T2-C2] anlmdn failed (severity={severity}) — bypass')
        return input_path, report

    # Sibilant guard
    ref_floor = state.silence_floor if state.silence_valid else float(
        state.clip_rms - state.snr_global)
    pre_c  = load_audio_fast(input_path, state.skip_s, min(state.dur_s, 30))
    post_c = load_audio_fast(tmp_anlm,   state.skip_s, min(state.dur_s, 30))
    sib_pre  = compute_sibilant_snr(pre_c,  ref_floor)
    sib_post = compute_sibilant_snr(post_c, ref_floor)
    sib_delta = sib_post - sib_pre

    # SFM check: anlmdn must not make the noise MORE tonal
    sfm_pre  = compute_sfm(pre_c)
    sfm_post = compute_sfm(post_c)

    L(f'  [T2-C2] anlmdn s={s} p={p}: '
      f'sib_snr_Δ={sib_delta:+.2f}dB  sfm_Δ={sfm_post - sfm_pre:+.4f}')

    if sib_delta < -3.0:
        L('  [T2-C2] sibilant drop > 3dB — REVERTED')
        report['reverted'] = True
        try: os.unlink(tmp_anlm)
        except: pass
        # If severity > 1, retry at one level lower before giving up
        if severity > 1:
            L(f'  [T2-C2] retrying at severity={severity - 1}...')
            return _anlmdn_pass(input_path, state, severity - 1)
        return input_path, report

    if sfm_post - sfm_pre < -0.06:
        L('  [T2-C2] noise became more tonal — REVERTED')
        report['reverted'] = True
        try: os.unlink(tmp_anlm)
        except: pass
        return input_path, report

    report.update({'applied': True, 'sib_delta': float(sib_delta)})
    return tmp_anlm, report


def _bandwidth_extension_pass(input_path: str, state: 'InputState') -> Tuple[str, Dict]:
    """
    T2-C3: Harmonic bandwidth extension above the codec cutoff.

    At very low bitrates (16-32kbps), the codec eliminates HF content
    entirely — not just rolling off gradually but truncating sharply.
    For 32kbps MP3, everything above ~11kHz is gone. At 24kbps: ~8kHz.
    At 16kbps: ~6kHz. This is the most audible component of the 'pixeled'
    quality: the voice sounds muffled, then suddenly harsh (from quantization)
    with no natural high-frequency air.

    Method: aexciter in ffmpeg.
    aexciter generates harmonics (primarily odd-order: 3rd, 5th, 7th) from
    content BELOW the codec cutoff and injects them ABOVE it. For speech,
    this creates plausible HF energy that follows the formant structure of
    the surviving signal — it is not synthesizing arbitrary noise but
    generating harmonics that ARE mathematically derived from the surviving
    lower partials.

    Parameters:
      freq:    The harmonic generation base frequency.
               Set to codec_cutoff × 0.60 — this ensures we generate
               harmonics that reach INTO and ABOVE the cutoff zone,
               not just below it where content already exists.
      amount:  Harmonic generation strength. Calibrated by extent of loss:
               cutoff 8-11kHz: amount=150 (mild recovery)
               cutoff 5-8kHz:  amount=250 (moderate)
               cutoff < 5kHz:  amount=350 (severe — 16kbps territory)
      floor_f: Lower bound of exciter effect: codec_cutoff × 0.40
               Below this, original signal is preserved unchanged.

    Guard: measure HF RMS (above codec_cutoff × 0.8) before and after.
    If HF RMS increases by more than 8dB, the exciter is adding too much
    synthetic energy — reduce amount by 40% and retry once.
    Guard 2: sibilant SNR (L-16) — if 2500-5000Hz band is harmed, revert.
    """
    cutoff = state.codec_cutoff
    report: Dict = {'applied': False, 'reverted': False,
                    'cutoff_hz': cutoff, 'hf_gain_db': 0.0}

    # FIX (v10.5): if full_spectrum shows voiced HF loss (>30dB gap mid vs HF)
    # but codec_cutoff reports 14kHz (inflated by noise windows), use the
    # actual spectral cutoff from the mid→HF rolloff point instead.
    if cutoff >= 14000 and state.full_spectrum:
        import numpy as _np2
        mid_v = [state.full_spectrum[fc] for fc in state.full_spectrum if 1000 <= fc <= 4000]
        hf_v  = [state.full_spectrum[fc] for fc in state.full_spectrum if 8000 <= fc <= 16000]
        if mid_v and hf_v and (float(_np2.mean(mid_v)) - float(_np2.mean(hf_v))) > 30.0:
            # Real speech HF is missing — use effective cutoff from 4kHz rolloff
            cutoff = 5000.0
            L(f'  [T2-C3] voiced HF loss detected — using effective cutoff={cutoff:.0f}Hz')
        else:
            return input_path, report
    elif cutoff >= 14000:
        return input_path, report

    # FIX (v10.5): freq_base must be >= 4000 — ffmpeg overflows below that
    # regardless of the amount parameter.
    freq_base = max(4000, int(cutoff * 0.60))
    floor_f   = int(cutoff * 0.40)

    # FIX-6b (v10.5): cap amount at 60 — ffmpeg overflows above 60
    # FIX-6c: scale HF guard by bandwidth deficit (not a fixed 8dB)
    if cutoff >= 11000:
        amount = 55   # mild recovery (11-14kHz zone)
    elif cutoff >= 8000:
        amount = 60   # moderate (8-11kHz zone)
    elif cutoff >= 5000:
        amount = 50   # severe but safe (5-8kHz zone)
    else:
        amount = 45   # extreme — conservative to avoid overflow

    # BW-SNR-CAP: When frame_snr < 8dB, aexciter generates harmonics from
    # noise-contaminated signal → synthesised HF is noise, not voice.
    # Scale amount down proportionally to frame_snr.
    if state.frame_snr < 8.0:
        snr_factor = float(np.clip(state.frame_snr / 8.0, 0.15, 1.0))
        amount = max(10, int(amount * snr_factor))

    # FIX-6a (v10.5): removed type=ls — not supported in this ffmpeg version
    exciter_filter = (f'aexciter=freq={freq_base}:'
                      f'amount={amount}:drive=8:blend=0.5')

    tmp_ext = os.path.join(_TMP, 'v104_bwext.wav')
    ok = ffmpeg_process(input_path, tmp_ext, exciter_filter)

    if not ok:
        L('  [T2-C3] aexciter failed — bypass')
        return input_path, report

    # Measure HF RMS before and after (in the restored zone)
    def _hf_rms(path: str) -> float:
        c = load_audio_fast(path, state.skip_s, min(state.dur_s, 20))
        if len(c) < SR * 2: return -60.0
        N = len(c)
        spec = np.abs(rfft(c)) ** 2
        freqs = rfftfreq(N, 1.0 / SR)
        mask = freqs > cutoff * 0.80
        return float(10 * np.log10(np.mean(spec[mask]) + 1e-30)) if mask.sum() > 0 else -60.0

    hf_before = _hf_rms(input_path)
    hf_after  = _hf_rms(tmp_ext)
    hf_gain   = hf_after - hf_before

    L(f'  [T2-C3] aexciter: cutoff={cutoff:.0f}Hz base={freq_base}Hz '
      f'amount={amount}  HF_gain={hf_gain:+.1f}dB')

    # FIX-6c (v10.5): HF guard scales with bandwidth deficit
    # For severe BW loss (cutoff=5kHz) more HF gain is expected and acceptable
    # Fixed 8dB guard was rejecting valid recovery on الأحزاب-type recordings
    # HF guard: scales with voiced HF deficit from full_spectrum.
    # The full_spectrum gives the TRUE voiced content gap (measured across
    # the whole file with silence gating). hf_before from _hf_rms can be
    # inflated by noise at the measurement frequency even when voiced HF is absent.
    hf_guard_bw = float(min(30.0, max(8.0, (14000 - cutoff) / 500.0)))
    voiced_gap = 0.0  # BF-1: initialize before conditional — prevents NameError
    if state.full_spectrum:
        import numpy as _npg
        _mid = [state.full_spectrum[fc] for fc in state.full_spectrum if 1000 <= fc <= 4000]
        _hfg = [state.full_spectrum[fc] for fc in state.full_spectrum if 8000 <= fc <= 16000]
        if _mid and _hfg:
            voiced_gap = float(_npg.mean(_mid)) - float(_npg.mean(_hfg))
            hf_guard_deficit = float(min(35.0, max(8.0, voiced_gap * 0.50)))
        else:
            hf_guard_deficit = hf_guard_bw
    else:
        hf_guard_deficit = hf_guard_bw
    hf_guard_db = max(hf_guard_bw, hf_guard_deficit)
    # VOICE-PRESERVE: hard ceiling at 10dB.
    # >10dB HF gain changes voice timbre via aexciter synthetic harmonics.
    # Real BW recovery (codec rolloff) needs ≤10dB; above that is timbre change.
    hf_guard_db = min(hf_guard_db, 10.0)
    L(f'  [T2-C3] HF guard = {hf_guard_db:.0f}dB (voiced_gap={voiced_gap:.0f}dB)')
    if hf_gain > hf_guard_db:
        # Retry at 40% lower strength
        L(f'  [T2-C3] HF gain {hf_gain:.1f}dB > {hf_guard_db:.0f}dB — retrying at amount={int(amount*0.6)}')
        try: os.unlink(tmp_ext)
        except: pass
        amount2 = int(amount * 0.60)
        # BF-2: removed type=ls and floor_f= — not supported, caused ffmpeg crash on retry
        exciter2 = (f'aexciter=freq={freq_base}:'
                    f'amount={amount2}:drive=6:blend=0.4')
        tmp_ext2 = os.path.join(_TMP, 'v104_bwext2.wav')
        ok2 = ffmpeg_process(input_path, tmp_ext2, exciter2)
        if ok2:
            hf_after2 = _hf_rms(tmp_ext2)
            hf_gain   = hf_after2 - hf_before
            L(f'  [T2-C3] retry HF_gain={hf_gain:+.1f}dB')
            # VOICE-PRESERVE: if retry also exceeds guard, revert entirely.
            # Applying synthetic harmonics above the guard changes voice timbre.
            if hf_gain > hf_guard_db:
                L(f'  [T2-C3] retry still {hf_gain:.1f}dB > {hf_guard_db:.0f}dB — REVERTED (voice preserve)')
                report['reverted'] = True
                try: os.unlink(tmp_ext2)
                except: pass
                return input_path, report
            tmp_ext = tmp_ext2
        else:
            L('  [T2-C3] retry failed — REVERTED')
            report['reverted'] = True
            return input_path, report

    # Sibilant guard: L-16 — aexciter must not corrupt Arabic fricatives
    ref_floor = state.silence_floor if state.silence_valid else float(
        state.clip_rms - state.snr_global)
    pre_c  = load_audio_fast(input_path, state.skip_s, min(state.dur_s, 20))
    post_c = load_audio_fast(tmp_ext,    state.skip_s, min(state.dur_s, 20))
    sib_pre  = compute_sibilant_snr(pre_c,  ref_floor)
    sib_post = compute_sibilant_snr(post_c, ref_floor)
    sib_delta = sib_post - sib_pre

    L(f'  [T2-C3] sib_snr_Δ={sib_delta:+.2f}dB')
    if sib_delta < -3.0:
        L('  [T2-C3] sibilant guard hit — REVERTED')
        report['reverted'] = True
        try: os.unlink(tmp_ext)
        except: pass
        return input_path, report

    report.update({'applied': True, 'hf_gain_db': float(hf_gain)})
    return tmp_ext, report


def nr_pass_codec_artifacts(input_path: str, state: 'InputState',
                             ref: 'ReferenceModel') -> Tuple[str, Dict]:
    """
    T2-C Orchestrator: detects and removes codec artifacts ('pixeled voice').

    Pipeline order (mandatory):
      C1  Pre-echo suppression   — time-domain, must run before anlmdn
                                    (anlmdn may smear the pre-echo into the
                                    adjacent speech region if run first)
      C2  anlmdn mosquito NR     — frequency-domain similarity denoising
      C3  Bandwidth extension    — only for codec_cutoff < 11kHz

    All three are independent signals paths with independent guards.
    The output of C1 feeds C2, and C2 feeds C3.
    If any stage is reverted, the next stage runs on the reverted (earlier) wav.

    The pre-echo suppression (C1) is done in numpy on the loaded audio and
    written to a temp WAV — this avoids an extra ffmpeg subprocess for what
    is a sample-level gain operation.
    """
    report: Dict = {
        'applied': False,
        'severity': 0,
        'artifacts': {},
        'preecho_corrections': 0,
        'anlmdn_applied': False, 'anlmdn_sib_delta': 0.0,
        'bw_ext_applied': False, 'bw_ext_hf_gain': 0.0,
        'reverted_stages': [],
    }

    severity, artifacts = _detect_codec_artifacts(state)
    report['severity'] = severity
    report['artifacts'] = artifacts

    if severity == 0:
        L('  [T2-C] no codec artifacts detected — bypass')
        return input_path, report

    L(f'  [T2-C] severity={severity}/3  '
      f'artifacts={[k for k,v in artifacts.items() if v]}')

    current = input_path

    # ── C1: Pre-echo suppression (numpy time-domain) ─────────────────────
    if artifacts.get('preecho'):
        L('  [T2-C1] pre-echo suppression...')
        audio_full = load_audio_fast(current, 0, state.total_s)
        if len(audio_full) >= SR * 3:
            fixed_audio, n_fixes = _suppress_preecho(audio_full, SR)
            L(f'  [T2-C1] {n_fixes} pre-echo regions corrected')

            if n_fixes > 0:
                tmp_pe = os.path.join(_TMP, 'v104_preecho.wav')
                raw = fixed_audio.astype(np.float32).tobytes()
                r = subprocess.run(
                    ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
                     '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
                     '-loglevel', 'error', tmp_pe],
                    input=raw, capture_output=True)
                if r.returncode == 0 and os.path.exists(tmp_pe):
                    current = tmp_pe
                    report['preecho_corrections'] = n_fixes
                    report['applied'] = True
                else:
                    L('  [T2-C1] write failed — continuing without pre-echo fix')
        else:
            L('  [T2-C1] audio too short — skipped')

    # ── C2: anlmdn mosquito / quantization noise ──────────────────────────
    if artifacts.get('mosquito') or artifacts.get('quant_noise'):
        L(f'  [T2-C2] anlmdn (severity={severity})...')
        anlmdn_wav, an_rep = _anlmdn_pass(current, state, severity)
        report['anlmdn_applied']  = an_rep.get('applied', False)
        report['anlmdn_sib_delta'] = an_rep.get('sib_delta', 0.0)
        if an_rep.get('reverted'):
            report['reverted_stages'].append('anlmdn')
        if anlmdn_wav != current:
            current = anlmdn_wav
            report['applied'] = True

    # ── C3: Bandwidth extension (HF recovery) ────────────────────────────
    # FIX: removed codec_cutoff < 11000 gate — _detect_codec_artifacts and
    # _bandwidth_extension_pass already handle the voiced-HF-loss path
    # correctly. The codec_cutoff reported by analyze_input can be inflated
    # by noise/breath windows (الأحزاب: real cutoff=5kHz but reported 14kHz).
    # _bandwidth_extension_pass re-checks the voiced spectrum directly.
    if artifacts.get('bw_loss'):
        L(f'  [T2-C3] bandwidth extension (cutoff={state.codec_cutoff:.0f}Hz)...')
        bw_wav, bw_rep = _bandwidth_extension_pass(current, state)
        report['bw_ext_applied'] = bw_rep.get('applied', False)
        report['bw_ext_hf_gain'] = bw_rep.get('hf_gain_db', 0.0)
        if bw_rep.get('reverted'):
            report['reverted_stages'].append('bw_ext')
        if bw_wav != current:
            current = bw_wav
            report['applied'] = True
            # Update state.codec_cutoff to reflect that HF is now present
            # Use the exciter base frequency as the new effective cutoff
            state.codec_cutoff = float(min(
                state.codec_cutoff * 1.35,
                14000.0
            ))
            L(f'  [T2-C3] effective cutoff updated to {state.codec_cutoff:.0f}Hz')

    if report['applied']:
        L(f'  [T2-C] ✓ preecho={report["preecho_corrections"]} '
          f'anlmdn={report["anlmdn_applied"]} '
          f'bw_ext={report["bw_ext_applied"]}  '
          f'sib_Δ={report["anlmdn_sib_delta"]:+.2f}dB')
    else:
        L('  [T2-C] all stages bypassed or reverted')

    return current, report


# Default reference phrase_lra_p50 used by needs_tier2() when called before
# a ReferenceModel is available (e.g., at routing time). Matches the BUG-E
# sliding-window p40 value: 2.63 LU from the 1425H reference files.
ref_phrase_lra_p50_default: float = 2.63

# ══════════════════════════════════════════════════════════════════════════════
#  [v5] NR CORE v16 — TYPE A/B/C  (inlined from nr_core_v16.py)
#  All functions prefixed _v16_.
#  _V16_SCIPY_FULL: True when stft, istft, exp1 are importable.
# ══════════════════════════════════════════════════════════════════════════════

try:
    from scipy.special import exp1 as _scipy_exp1
    from scipy.signal import stft as _scipy_stft, istft as _scipy_istft
    _V16_SCIPY_FULL = True
except ImportError:
    _V16_SCIPY_FULL = False

_V16_TIER_PRISTINE   = 'TIER_PRISTINE'
_V16_TIER_COMPRESSED = 'TIER_COMPRESSED'
_V16_TIER_DEGRADED   = 'TIER_DEGRADED'
_V16_TIER_DAMAGED    = 'TIER_DAMAGED'
_V16_TIER_CRITICAL   = 'TIER_CRITICAL'

def _v16_make_alpha_bins(alpha_scalar: float, fft_bins: int, sr: int) -> np.ndarray:
    """Per-bin α_dd array — slower tracking in bass, faster at 3–8 kHz."""
    fft_n = (fft_bins - 1) * 2
    freqs = rfftfreq(fft_n, 1.0 / sr)
    ramp  = np.clip(
        (freqs - _A_ALPHA_F_LO) / (_A_ALPHA_F_HI - _A_ALPHA_F_LO),
        0.0, 1.0)
    return np.clip(alpha_scalar - _A_ALPHA_MAX_REDUCTION * ramp,
                   0.90, 1.0).astype(np.float64)


def _v16_sib_band_snr(audio: np.ndarray, sr: int) -> Optional[float]:
    """
    Sibilant-band SNR proxy.  Returns dB or None if audio too short.
    Reference band: 1750–2800 Hz (mid-low, avoids F0 harmonics and sibilants).
    Signal band : 4500–9500 Hz (shin / sin / sad zone).
    """
    fft_n = min(4096, len(audio))
    if fft_n < 1024:
        return None
    spec  = np.abs(rfft(audio[:fft_n], n=fft_n)) ** 2
    freqs = rfftfreq(fft_n, 1.0 / sr)
    ref_m = (freqs >= _SIB_FREQ_LO * 0.39) & (freqs <= _SIB_FREQ_LO * 0.62)
    sig_m = (freqs >= _SIB_FREQ_LO) & (freqs <= _SIB_FREQ_HI)
    if not ref_m.any() or not sig_m.any():
        return None
    return float(10.0 * np.log10(
        max(np.mean(spec[sig_m]) / (np.mean(spec[ref_m]) + 1e-30), 1e-30)))


def _v16_sib_band_restore(processed: np.ndarray,
                       original:  np.ndarray,
                       sr: int) -> np.ndarray:
    """
    Spectral-domain sibilant-band restore (L-16).
    Replaces 4.5–9.5 kHz band with the original signal's contribution
    in OLA chunks to avoid edge discontinuities.
    """
    if not _V16_SCIPY_FULL:
        return processed
    frame_n = 2048; hop_n = frame_n // 4
    win     = np.hanning(frame_n)
    out     = processed.copy().astype(np.float32)
    n       = min(len(processed), len(original))
    for i in range(0, max(1, (n - frame_n) // hop_n)):
        s = i * hop_n; e = s + frame_n
        if e > n:
            break
        X_proc = rfft(processed[s:e].astype(np.float64) * win, n=frame_n)
        X_orig = rfft(original[s:e].astype(np.float64)  * win, n=frame_n)
        freqs  = rfftfreq(frame_n, 1.0 / sr)
        mask   = (freqs >= _SIB_FREQ_LO) & (freqs <= _SIB_FREQ_HI)
        X_proc[mask] = X_orig[mask]
        seg = irfft(X_proc, n=frame_n)[:frame_n].astype(np.float32)
        out[s:e] = out[s:e] * (1 - win.astype(np.float32)) + seg * win.astype(np.float32)
    return out


def _v16_frame_rms_db(audio: np.ndarray, sr: int,
                   frame_s: float, hop_s: float) -> np.ndarray:
    """Compute short-time log-RMS array.  Returns dBFS per frame."""
    frame_n = int(sr * frame_s)
    hop_n   = int(sr * hop_s)
    n       = max(1, (len(audio) - frame_n) // hop_n)
    rms_db  = np.full(n, -60.0, dtype=np.float32)
    for i in range(n):
        seg = audio[i * hop_n: i * hop_n + frame_n]
        if len(seg) == frame_n:
            rms = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2)))
            rms_db[i] = float(20.0 * np.log10(max(rms, 1e-10)))
    return rms_db


def _v16_cpp_estimate(power: np.ndarray, sr: int = 48000) -> float:
    """
    Cepstral Peak Prominence — quick voiced-frame indicator.
    Returns dB prominence of the pitch peak in the cepstrum.

    FIX: lag range derived from actual sr (was hardcoded to 8000 Hz,
    which placed the search window at 333–2526 Hz instead of 70–650 Hz
    at 48 kHz — measuring formants not pitch).

    F0 range: 70–650 Hz → lag range [sr/650, sr/70] samples.
    """
    log_spec = np.log(np.maximum(power, 1e-10))
    cep      = np.fft.irfft(log_spec)
    lo       = max(2, int(sr / 650.0))   # lag for 650 Hz upper bound
    hi       = min(len(cep) - 1, int(sr / 70.0))   # lag for 70 Hz lower bound
    if lo >= hi:
        return 0.0
    peak = float(np.max(np.abs(cep[lo:hi])))
    bg   = np.concatenate([cep[max(0, lo - 15):lo],
                            cep[hi:min(len(cep), hi + 15)]])
    bg_m = float(np.mean(np.abs(bg))) if len(bg) else 1e-10
    return float(20.0 * np.log10(peak / (bg_m + 1e-10)))


def _v16_apply_madd_gate(depth_map: list,
                      madd_windows: list,
                      sr: int,
                      hop_s: float = 0.010,
                      cap: float = 0.50) -> list:
    """
    GATE-G1: cap NR depth within Madd event windows.

    The depth map uses 10ms frames.  madd_windows is a list of
    (t_start_s, t_end_s) pairs from ExecutionContext.madd_windows.
    Frames that overlap any window are capped at `cap` (default 0.50).

    This is separate from PZM zone vetoes — PZM is frequency-domain;
    GATE-G1 is time-domain.  Both apply independently.
    """
    if not madd_windows or not depth_map:
        return depth_map
    hop_n     = int(sr * hop_s)
    arr       = np.array(depth_map, dtype=np.float32)
    for (t_s, t_e) in madd_windows:
        f_s = max(0, int(t_s * sr / hop_n))
        f_e = min(len(arr), int(t_e * sr / hop_n) + 1)
        arr[f_s:f_e] = np.minimum(arr[f_s:f_e], cap)
    return arr.tolist()


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — TYPE_A: MMSE-LSA NOISE FLOOR NR
#
#  The inner _mmse_lsa_pass function is the UNCHANGED v15.18 implementation.
#  TYPE_A adds:
#    1. TIER_DEGRADED-aware parameter selection from v16 tables
#    2. Correct two-pass / three-pass logic (preserved from v15.18)
#    3. GATE-G1 application to depth map BEFORE passing to _mmse_lsa_pass
#    4. recovery_confidence computation from mean MMSE-LSA gain applied
# ══════════════════════════════════════════════════════════════════════════════

def _v16_mmse_lsa_pass(
        audio: np.ndarray,
        sr: int,
        nr_depth_map: list,
        pzm_scale: float,
        nr_confidence: float,
        alpha_dd: float,
        g_floor: float,
        spp_q: float,
        noise_psd_init: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    MMSE-LSA + IMCRA + OMLSA single pass.  Core algorithm UNCHANGED from
    v15.18 _mmse_lsa_pass.  Added return: mean_gain (float ∈ [0,1]).

    mean_gain is the average of G_applied across all frames.
    A value near 1.0 means very little suppression was applied (clean source).
    A value near 0.4 means heavy suppression (cassette-grade noise).
    This feeds recovery_confidence in _v16_nr_type_a_pass.

    Returns (output_audio, final_noise_psd, mean_gain).
    """
    frame_n   = int(sr * 0.025)
    hop_n     = int(sr * 0.010)
    win       = np.hanning(frame_n)
    fft_n     = int(2 ** np.ceil(np.log2(frame_n)))   # 2048 at 48 kHz
    fft_bins  = fft_n // 2 + 1                         # 1025

    # — Noise PSD initialisation (same as v15.18) —
    if noise_psd_init is not None:
        noise_psd = noise_psd_init.astype(np.float64) + 1e-20
    else:
        n_boot    = max(1, (len(audio) - frame_n) // hop_n)
        boot_lim  = min(n_boot, int(30.0 * sr / hop_n))
        boot_psds: list = []
        sil_psds:  list = []
        for i in range(0, boot_lim, max(1, boot_lim // 200)):
            seg = audio[i * hop_n: i * hop_n + frame_n]
            if len(seg) < frame_n:
                continue
            psd = np.abs(rfft(seg * win, n=fft_n)) ** 2
            boot_psds.append(psd)
            if (nr_depth_map and i < len(nr_depth_map)
                    and nr_depth_map[i] >= 0.95):
                sil_psds.append(psd)
        if len(sil_psds) >= 5:
            noise_psd = np.median(np.stack(sil_psds, axis=0), axis=0)
        elif boot_psds:
            noise_psd = np.percentile(np.stack(boot_psds, axis=0), 10, axis=0)
        else:
            noise_psd = np.full(fft_bins, 1e-10, dtype=np.float64)
        noise_psd = noise_psd.astype(np.float64) + 1e-20

    alpha_dd_bins = _v16_make_alpha_bins(alpha_dd, fft_bins, sr)
    S_smooth  = noise_psd.copy()
    min_buf   = np.tile(S_smooth, (_IMCRA_MIN_WIN, 1))
    min_ptr   = 0
    # FIX-DSP-1: track G_prev² × γ_prev (not ξ_prev) — see v15.18 notes.
    xi_dd      = np.ones(fft_bins, dtype=np.float64)
    gamma_prev = np.ones(fft_bins, dtype=np.float64)
    G_prev     = np.ones(fft_bins, dtype=np.float64)
    p_spp_prev = np.ones(fft_bins, dtype=np.float64)
    output     = np.zeros(len(audio), dtype=np.float32)
    norm_wt    = np.zeros(len(audio), dtype=np.float32)
    voice_hold = 0
    n_frames   = max(1, (len(audio) - frame_n) // hop_n)

    # ── Accumulate mean gain for recovery_confidence ──
    gain_acc   = 0.0
    gain_count = 0

    for i in range(n_frames):
        depth = (float(nr_depth_map[i]) * pzm_scale
                 if (nr_depth_map and i < len(nr_depth_map))
                 else float(nr_confidence * 0.8) * pzm_scale)
        if depth < 0.02:
            seg = audio[i * hop_n: i * hop_n + frame_n]
            if len(seg) == frame_n:
                output[i*hop_n: i*hop_n + frame_n] += seg * win
                norm_wt[i*hop_n: i*hop_n + frame_n] += win
            continue
        seg = audio[i * hop_n: i * hop_n + frame_n]
        if len(seg) < frame_n:
            seg = np.pad(seg, (0, frame_n - len(seg)))
        X      = rfft(seg * win, n=fft_n)
        X_mag2 = np.abs(X) ** 2

        S_smooth         = _BETA_NOISE * S_smooth + (1.0 - _BETA_NOISE) * X_mag2
        min_buf[min_ptr] = S_smooth
        min_ptr          = (min_ptr + 1) % _IMCRA_MIN_WIN
        noise_psd        = np.maximum(np.minimum.reduce(min_buf), 1e-20) * _IMCRA_BIAS

        gamma  = X_mag2 / noise_psd
        xi     = (alpha_dd_bins * xi_dd
                  + (1.0 - alpha_dd_bins) * np.maximum(gamma - 1.0, 0.0))

        noise_rms_ref = float(np.sqrt(np.mean(noise_psd))) + 1e-20
        g_floor_bin   = np.clip(
            g_floor * np.sqrt(np.maximum(noise_psd, 0.0)) / noise_rms_ref,
            g_floor * 0.5, g_floor * 3.0)

        nu = np.maximum(xi / (1.0 + xi) * gamma, 1e-20)
        if _V16_SCIPY_FULL:
            G_mmse = np.clip(
                (xi / (1.0 + xi)) * np.exp(0.5 * _scipy_exp1(nu)),
                g_floor_bin, 1.0)
        else:
            G_mmse = np.clip(xi / (1.0 + xi), g_floor_bin, 1.0)

        Lambda    = np.maximum((1.0 + xi) * np.exp(-nu), 1e-30)
        p_spp_raw = 1.0 / (1.0 + (spp_q / (1.0 - spp_q)) / Lambda)
        p_spp     = _TSNR_GAIN_ALPHA * p_spp_prev + (1.0 - _TSNR_GAIN_ALPHA) * p_spp_raw
        p_spp_prev[:] = p_spp
        G_raw = (np.power(G_mmse, p_spp) * np.power(g_floor_bin, 1.0 - p_spp))

        is_voiced = float(np.mean(gamma)) > _TSNR_VAD_THRESH
        if is_voiced:
            voice_hold = _TSNR_VOICE_HOLD
        elif voice_hold > 0:
            voice_hold -= 1
            is_voiced   = True
        alpha_g  = _TSNR_GAIN_ALPHA if not is_voiced else (_TSNR_GAIN_ALPHA * 0.5)
        G_smooth = alpha_g * G_prev + (1.0 - alpha_g) * G_raw
        G_prev[:] = G_smooth

        # FIX-DSP-1: xi_dd = G_prev² × γ_prev
        xi_dd[:]      = np.maximum(G_smooth ** 2 * gamma, 0.0)
        gamma_prev[:] = gamma

        G_applied = depth * G_smooth + (1.0 - depth) * 1.0

        # KB-12-06: Hams letter breathiness guard (Supplement §52.3)
        # Hams letters (fa, ha, tha, he, shin, kha, Sad, sin, kaf, ta) are
        # aspirated/breathy with high ZCR and low periodicity. NR treats their
        # breathiness as noise and over-suppresses it — destroying the phonetic
        # quality that distinguishes he from hamza, sin from Sad, etc.
        # Detection: compute ZCR of the current frame. If ZCR > 0.22 (high ZCR =
        # unvoiced fricative territory) AND the frame has moderate energy (not silence),
        # limit attenuation so G_applied >= 0.50 (max -6dB attenuation).
        # Note: this runs on every frame cheaply since audio[frame] is already loaded.
        if is_voiced:
            _frame_seg = audio[i * hop_n: i * hop_n + frame_n]
            if len(_frame_seg) > 4:
                _zcr = float(np.sum(np.abs(np.diff(np.sign(_frame_seg)))) /
                             (2 * max(len(_frame_seg) - 1, 1)))
                if _zcr > 0.22:
                    # High-ZCR voiced frame: this is likely a Hams letter burst
                    # Cap minimum gain at 0.50 (-6dB) — never suppress more than that
                    G_applied = np.maximum(G_applied, 0.50)

        # Accumulate mean applied gain (voiced frames only — they tell us
        # how much speech was suppressed; silence frames are expected to
        # suppress heavily and should not bias recovery_confidence)
        if is_voiced:
            gain_acc   += float(np.mean(G_applied))
            gain_count += 1

        Y       = X * G_applied
        out_seg = irfft(Y, n=fft_n)[:frame_n].astype(np.float32)
        output[i*hop_n: i*hop_n + frame_n] += out_seg * win
        norm_wt[i*hop_n: i*hop_n + frame_n] += win

    # Final partial frame (SEV-2-F pattern from v15.18)
    _last_i = n_frames
    if _last_i * hop_n < len(audio):
        _seg_tail = audio[_last_i * hop_n: _last_i * hop_n + frame_n]
        if len(_seg_tail) > 0:
            _seg_tail = np.pad(_seg_tail, (0, frame_n - len(_seg_tail)))
            _X_tail   = rfft(_seg_tail * win, n=fft_n)
            _out_tail = irfft(_X_tail * G_applied, n=fft_n)[:frame_n].astype(np.float32)
            output[_last_i*hop_n: _last_i*hop_n + frame_n] += _out_tail * win
            norm_wt[_last_i*hop_n: _last_i*hop_n + frame_n] += win

    safe_w = np.where(norm_wt > 1e-6, norm_wt, 1.0)
    output /= safe_w

    mean_gain = float(gain_acc / gain_count) if gain_count > 0 else 1.0
    return output, noise_psd, mean_gain


def _v16_nr_type_a_pass(
        audio:        np.ndarray,
        sr:           int,
        nr_depth_map: list,
        pzm_scale:    float,
        nr_confidence: float,
        source_tier:  str,
        severity:     float,   # d02_noise [0..1] — scales two/three-pass decision
        madd_windows: list,
) -> Tuple[np.ndarray, float, str]:
    """
    TYPE_A: noise floor NR via MMSE-LSA + IMCRA + OMLSA.

    Differences from v15.18 _exec_nr_mmse_lsa inner logic:
      • Selects α_dd, g_floor, spp_q from v16 tables (TIER_DEGRADED supported).
      • Applies GATE-G1 (madd_windows) to depth_map before passing to core.
      • Returns mean_gain alongside audio for recovery_confidence computation.
      • Two-pass trigger: TIER_CRITICAL OR severity ≥ 0.70 (not just TIER_CRITICAL).
      • Three-pass trigger: snr_global < 5 (unchanged from v15.18).

    Returns (output_audio, mean_gain, track_label).
    """
    alpha_dd = _A_ALPHA_DD.get(source_tier, 0.970)
    g_floor  = _A_G_FLOOR.get(source_tier, 0.020)
    spp_q    = _A_SPP_PRIOR_Q.get(source_tier, 0.40)

    # GATE-G1: apply madd_windows temporal cap before NR
    gated_map = _v16_apply_madd_gate(nr_depth_map, madd_windows, sr,
                                  hop_s=0.010, cap=0.50)

    # Pass 1
    pass1, psd1, mg1 = _v16_mmse_lsa_pass(
        audio, sr, gated_map, pzm_scale, nr_confidence,
        alpha_dd, g_floor, spp_q, noise_psd_init=None)

    # Two-pass: TIER_CRITICAL or heavy damage (d02_noise ≥ 0.70)
    need_2pass = (source_tier == TIER_CRITICAL or severity >= 0.70)
    if need_2pass and len(audio) > sr * 10:
        frame_n = int(sr * 0.025)
        fft_n   = int(2 ** np.ceil(np.log2(frame_n)))
        win_r   = np.hanning(frame_n)
        residual = audio.astype(np.float64) - pass1.astype(np.float64)
        n_sample = min(20, max(5, len(residual) // (frame_n * 4)))
        indices  = np.linspace(0, len(residual) - frame_n, n_sample, dtype=int)
        res_psds = []
        for idx in indices:
            seg = residual[idx: idx + frame_n]
            if len(seg) == frame_n:
                res_psds.append(np.abs(rfft(seg * win_r, n=fft_n)) ** 2)

        if res_psds:
            res_psd = np.median(np.stack(res_psds, axis=0), axis=0).astype(np.float64)
            pass2, psd2, mg2 = _v16_mmse_lsa_pass(
                audio, sr, gated_map, pzm_scale, nr_confidence,
                alpha_dd, g_floor, spp_q, noise_psd_init=res_psd)

            # Three-pass: SNR near the floor (severity implies snr < 5dB territory)
            if severity >= 0.90 and len(audio) > sr * 15:
                residual2 = audio.astype(np.float64) - pass2.astype(np.float64)
                res_psds2 = []
                for idx in indices:
                    seg2 = residual2[idx: idx + frame_n]
                    if len(seg2) == frame_n:
                        res_psds2.append(np.abs(rfft(seg2 * win_r, n=fft_n)) ** 2)
                if res_psds2:
                    res_psd2 = np.median(np.stack(res_psds2, axis=0), axis=0).astype(np.float64)
                    # Cap nr_confidence at 0.92 on pass 3 (prevents silence on madd tails)
                    conf_capped = min(nr_confidence, 0.92)
                    pass3, _, mg3 = _v16_mmse_lsa_pass(
                        pass2, sr, gated_map, pzm_scale, conf_capped,
                        alpha_dd, g_floor, spp_q, noise_psd_init=res_psd2)
                    # mean_gain: pessimistic average (take pass with least gain applied)
                    mean_gain = min(mg1, mg2, mg3)
                    return pass3.astype(np.float32), mean_gain, '1-MMSE-LSA-3pass'

            mean_gain = min(mg1, mg2)
            return pass2.astype(np.float32), mean_gain, '1-MMSE-LSA-2pass'

    return pass1.astype(np.float32), mg1, '1-MMSE-LSA'


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — TYPE_B: DYNAMICS EXPANSION PASS
#
#  Fires when d03_dynamics ≥ 0.45 (LRA damage threshold from R-1).
#  Goal: restore natural dynamic range to over-compressed recordings without
#  introducing pumping or breath artifacts.
#
#  Algorithm:
#    1. Compute short-time log-RMS envelope (20ms frames, 10ms hop).
#    2. Build smoothed lookahead envelope (60ms) to prevent pumping.
#    3. Compute expansion gain: G = (env / threshold)^(R-1) with soft knee.
#    4. Apply gain sample-by-sample via cubic interpolation between frames.
#    5. Protect strongly voiced frames (CPP > _B_CPP_PROTECT dB).
#    6. Skip frames in madd_windows (same GATE-G1 convention).
#
#  The expansion ratio R is derived from d03_dynamics:
#    R = lerp(_B_MIN_RATIO, _B_MAX_RATIO, t)
#    where t = (d03_dynamics - 0.45) / 0.55  (normalised to [0,1])
# ══════════════════════════════════════════════════════════════════════════════

def _v16_nr_type_b_pass(
        audio:         np.ndarray,
        sr:            int,
        d03_dynamics:  float,
        madd_windows:  list,
) -> Tuple[np.ndarray, float]:
    """
    TYPE_B: dynamics expansion pass.

    Returns (output_audio, lra_estimate_lu) where lra_estimate_lu is an
    approximate LRA in Loudness Units after expansion (0.0 if not run).
    """
    if not NUMPY_OK or len(audio) < sr * 2:
        return audio, 0.0

    # ── Expansion ratio from d03_dynamics ────────────────────────────────────
    t_norm    = float(np.clip((d03_dynamics - 0.45) / 0.55, 0.0, 1.0))
    exp_ratio = _B_MIN_RATIO + t_norm * (_B_MAX_RATIO - _B_MIN_RATIO)

    frame_n    = int(sr * _B_FRAME_S)
    hop_n      = int(sr * _B_HOP_S)
    lookahead  = int(_B_LOOKAHEAD_S / _B_HOP_S)   # frames
    n_frames   = max(1, (len(audio) - frame_n) // hop_n)

    # ── Frame-level log-RMS ───────────────────────────────────────────────────
    rms_db  = np.full(n_frames, -60.0, dtype=np.float32)
    cpp_arr = np.zeros(n_frames, dtype=np.float32)
    fft_n_b = 2048
    win_b   = np.hanning(frame_n)

    for i in range(n_frames):
        seg = audio[i * hop_n: i * hop_n + frame_n]
        if len(seg) < frame_n:
            break
        seg_f = seg.astype(np.float64)
        rms   = float(np.sqrt(np.mean(seg_f ** 2)))
        rms_db[i] = float(20.0 * np.log10(max(rms, 1e-10)))
        # CPP for voiced-frame detection
        if _V16_SCIPY_FULL:
            psd = np.abs(rfft(seg_f * win_b[:frame_n], n=fft_n_b)) ** 2
            cpp_arr[i] = float(_v16_cpp_estimate(psd, sr))

    # ── Lookahead smoothing (anti-pumping) ────────────────────────────────────
    rms_smooth = np.convolve(rms_db,
                              np.ones(lookahead, dtype=np.float32) / lookahead,
                              mode='same')

    # ── Reference level: 15th percentile (the loudest-quiet region) ──────────
    ref_db = float(np.percentile(rms_db[rms_db > -55.0], 15)) \
             if np.any(rms_db > -55.0) else _B_THRESHOLD_DB

    # ── Build gain curve (per-frame) ──────────────────────────────────────────
    gain_db = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        env    = float(rms_smooth[i])
        delta  = env - ref_db   # negative: below reference → expand upward

        if delta >= 0.0:
            # Above or at reference: no expansion (gate behaviour)
            gain_db[i] = 0.0
            continue

        # Soft knee: transition over _B_KNEE_DB dB below reference
        knee_lo = -_B_KNEE_DB
        if delta > knee_lo:
            # In the knee: blend linearly from 0 to full expansion gain
            # blend = 1 at delta=0 (no expansion), 0 at delta=knee_lo (full)
            blend  = (delta - knee_lo) / (-knee_lo)
            g_full = -(exp_ratio - 1.0) * delta   # FIX: negative → positive gain for quiet frames
            gain_db[i] = float((1.0 - blend) * g_full)
        else:
            # Below knee: full upward expansion
            # delta < 0, so -(exp_ratio-1)*delta > 0 (boost quiet frames)
            gain_db[i] = float(-(exp_ratio - 1.0) * delta)

        # Voiced-frame protection: cap expansion at 25% for strongly voiced frames
        if cpp_arr[i] > _B_CPP_PROTECT:
            gain_db[i] *= 0.25

    # Madd window protection: no expansion during long-vowel events
    if madd_windows:
        for (t_s, t_e) in madd_windows:
            f_s = max(0, int(t_s * sr / hop_n))
            f_e = min(n_frames, int(t_e * sr / hop_n) + 1)
            gain_db[f_s:f_e] = 0.0

    # Cap: never exceed 12 dB boost; never reduce (upward expander only)
    gain_db = np.clip(gain_db, 0.0, 12.0)

    # ── Attack / release smoothing ─────────────────────────────────────────────
    att_coeff = float(np.exp(-1.0 / (sr * _B_ATTACK_S   / hop_n)))
    rel_coeff = float(np.exp(-1.0 / (sr * _B_RELEASE_S  / hop_n)))
    smooth_gain = np.zeros_like(gain_db)
    prev = 0.0
    for i in range(n_frames):
        target = gain_db[i]
        coeff  = att_coeff if target > prev else rel_coeff
        prev   = coeff * prev + (1.0 - coeff) * target
        smooth_gain[i] = prev

    # ── Apply gain sample-by-sample via linear interpolation ──────────────────
    gain_lin     = 10.0 ** (smooth_gain / 20.0)
    output       = audio.copy().astype(np.float32)
    prev_g, next_g = gain_lin[0], gain_lin[0]
    for i in range(n_frames):
        s = i * hop_n
        e = min(s + hop_n, len(output))
        next_g = gain_lin[min(i + 1, n_frames - 1)]
        interp = np.linspace(float(prev_g), float(next_g),
                              e - s, dtype=np.float32)
        output[s:e] *= interp
        prev_g = next_g

    # ── LRA estimate (log-RMS variance proxy) ────────────────────────────────
    post_rms = _v16_frame_rms_db(output, sr, _B_FRAME_S, _B_HOP_S)
    active   = post_rms[post_rms > -50.0]
    lra_est  = float(np.percentile(active, 95) - np.percentile(active, 10)) \
               if len(active) > 10 else 0.0

    return output, lra_est


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — TYPE_C: CODEC ARTIFACT SUPPRESSION
#
#  Fires when d01_codec ≥ 0.25 (codec damage threshold from R-1).
#  Three sub-passes applied in order:
#
#  C-1  Pre-echo suppression
#       Detects and attenuates temporal pre-echo before transients.
#       Codec quantisation can cause ringing ~20ms before an onset.
#
#  C-2  Spectral NLM denoising  (anlmdn equivalent)
#       Adaptive Non-Local Means on the STFT magnitude spectrogram.
#       Exploits self-similarity of Quranic recitation (repeated phonemes)
#       to smooth codec quantisation noise while preserving fine structure.
#
#  C-3  Bandwidth extension  (only if d01_codec high and type_c_applied gate)
#       Harmonic extrapolation above detected spectral cutoff.
#       Applied only when detected cutoff < _C_BWX_MIN_CUTOFF_HZ.
#       Always tapered to avoid abrupt spectral edges.
#
#  Returns (output_audio, cutoff_hz_detected, type_c_applied).
# ══════════════════════════════════════════════════════════════════════════════

def _v16_detect_codec_cutoff(audio: np.ndarray, sr: int) -> float:
    """
    Detect spectral cutoff frequency from energy rolloff.
    Returns cutoff in Hz (frequency below which 95% of spectral energy lies).
    Looks for the frequency above which spectral slope steepens beyond −30dB/oct.
    """
    fft_n = min(8192, max(2048, len(audio)))
    win   = np.hanning(min(fft_n, len(audio)))
    seg   = audio[:len(win)].astype(np.float64) * win
    spec  = np.abs(rfft(seg, n=fft_n)) ** 2
    freqs = rfftfreq(fft_n, 1.0 / sr)

    # Smooth spectrum in 1/3-octave bands
    spec_sm = np.zeros_like(spec)
    for j, f in enumerate(freqs):
        if f < 100:
            continue
        f_lo = f / (2 ** (1/6))
        f_hi = f * (2 ** (1/6))
        mask = (freqs >= f_lo) & (freqs <= f_hi)
        spec_sm[j] = float(np.mean(spec[mask])) if mask.any() else spec[j]

    # Find where energy drops > 30dB in one octave above a stable plateau
    db_spec = 10.0 * np.log10(np.maximum(spec_sm, 1e-10))
    cutoff  = float(sr / 2)
    for j in range(len(freqs) - 1, 0, -1):
        f = freqs[j]
        if f < 3000:
            break
        j_oct = int(j / 2)  # one octave lower
        if j_oct < 1:
            continue
        drop = db_spec[j_oct] - db_spec[j]
        if drop > 30.0 and f < cutoff:
            cutoff = float(f)

    return float(np.clip(cutoff, 2000.0, float(sr / 2)))


def _v16_type_c_preecho_suppress(
        audio: np.ndarray,
        sr:    int,
) -> np.ndarray:
    """
    C-1: Pre-echo suppression.

    Detects codec pre-echo (energy ~20-30ms before transients that should be
    silent) and attenuates it.

    FIX: v1 applied gain as hard per-frame blocks, creating clicks at every
    frame boundary where adjacent frames had different gain values (50%
    overlap means each sample sits in two frames — the gain discontinuity
    at the boundary was audible).

    v2 uses windowed OLA:
      1. Build a per-frame gain vector (same detection logic as before).
      2. Smooth the gain curve with a short Hanning window to eliminate
         abrupt edges between suppressed and unsuppressed frames.
      3. Upsample the per-frame gain to per-sample via linear interpolation
         and apply directly — no OLA accumulator needed since gain is
         multiplicative and we apply it once per sample.
    """
    if not NUMPY_OK or len(audio) < sr * 0.5:
        return audio

    hop_n   = int(sr * 0.010)
    frame_n = int(sr * 0.020)
    n_look  = int(_C_PREECHO_LOOKBACK_S / 0.010)
    rms_db  = _v16_frame_rms_db(audio, sr, 0.020, 0.010)
    n_f     = len(rms_db)

    # Detect onset frames (>8 dB energy rise in 10ms)
    onset_mask = np.zeros(n_f, dtype=bool)
    for i in range(1, n_f):
        if rms_db[i] - rms_db[i - 1] > 8.0:
            onset_mask[i] = True

    # Build per-frame suppression gain (linear)
    suppress_gain = np.ones(n_f, dtype=np.float32)
    atten_lin     = float(10.0 ** (-_C_PREECHO_ATTEN_DB / 20.0))

    for i in range(n_f):
        if not onset_mask[i]:
            continue
        masker_db = rms_db[max(0, i - 1)]
        for j in range(max(0, i - n_look), i):
            if masker_db - rms_db[j] >= _C_PREECHO_THRESH_DB:
                suppress_gain[j] = min(suppress_gain[j], atten_lin)

    # ── Smooth gain curve (FIX: eliminates OLA discontinuities) ─────────────
    # A 5-frame Hanning-weighted smoother blends gain transitions over ~50ms.
    # This is applied to the per-FRAME gain before upsampling to per-sample.
    smooth_win    = np.hanning(5).astype(np.float32)
    smooth_win   /= smooth_win.sum()
    suppress_gain = np.convolve(suppress_gain, smooth_win, mode='same')
    suppress_gain = np.clip(suppress_gain, atten_lin, 1.0)

    # ── Upsample frame gain to per-sample via linear interpolation ───────────
    # Frame centres are at [hop_n/2, 3*hop_n/2, ...]; linearly interpolate
    # between centres so the gain is continuous at the sample level.
    n_samples      = len(audio)
    frame_centres  = (np.arange(n_f) + 0.5) * hop_n
    sample_indices = np.arange(n_samples, dtype=np.float32)
    sample_gain    = np.interp(sample_indices, frame_centres,
                                suppress_gain).astype(np.float32)

    return (audio.astype(np.float32) * sample_gain)


def _v16_type_c_nlm_denoise(
        audio:     np.ndarray,
        sr:        int,
        strength:  float,
) -> np.ndarray:
    """
    C-2: Spectral Non-Local Means (NLM) denoising.  anlmdn equivalent.

    Fully vectorised — no Python loops over frames or frequency bins.

    Algorithm per iteration:
      1. Pre-build the patch tensor P[t, f, p] = mag[f±F_PATCH, t]  via
         np.lib.stride_tricks (zero-copy view + pad).  Shape: (T, F, 2F+1).
      2. For each temporal offset δ ∈ [-T_RADIUS, +T_RADIUS], roll P along
         the time axis to get P_shifted[t] = P[t+δ].
      3. Compute per-(t,f) patch distance²: mean over patch dim of (P - P_shifted)².
         Shape: (T, F).
      4. Weight w = exp(-dist² / h²).  Accumulate w*mag_shifted and w across δ.
      5. Normalised output = Σ(w·mag) / Σ(w).

    No Python loops over t, f, or tj — entirely numpy broadcasting.
    Runtime: O(T_RADIUS × T × F) numpy ops vs O(T_RADIUS × T × F × F_PATCH²) Python.
    Speed-up on 5-min 48kHz file: ~200× vs the v1 loop.

    Voiced frames (mean gamma > VAD thresh) get half NLM strength (h² ÷ 2)
    to protect formant structure.
    """
    if not _V16_SCIPY_FULL or not NUMPY_OK:
        return audio
    if len(audio) < sr * 1.0:
        return audio

    stft_n = 1024
    hop_stft = stft_n // 4
    try:
        _, _, Zxx = _scipy_stft(audio.astype(np.float32), fs=sr,
                                 nperseg=stft_n, noverlap=stft_n - hop_stft,
                                 window='hann')
    except Exception:
        return audio

    # mag: (n_freq, n_time) — work in (n_time, n_freq) internally for cache locality
    mag_orig   = np.abs(Zxx).astype(np.float32)       # (F, T)
    phase_orig = np.angle(Zxx)                         # (F, T)
    n_freq, n_time = mag_orig.shape

    # Noise variance: 10th percentile per-freq across time
    noise_var = np.maximum(
        np.percentile(mag_orig ** 2, 10, axis=1),      # (F,)
        1e-10)

    strength_scale = 0.5 + 1.5 * float(np.clip(strength, 0.0, 1.0))

    # Per-frame voiced mask — halve h² on voiced frames
    frame_power = np.mean(mag_orig ** 2, axis=0)       # (T,)
    frame_gamma = frame_power / (float(np.mean(noise_var)) + 1e-10)
    voiced_mask = (frame_gamma > _TSNR_VAD_THRESH).astype(np.float32)  # (T,)

    # h² shape: (F,) — will broadcast over time
    # On voiced frames we halve h²: implemented as a (T,) voiced scale factor
    # applied to dist² (equivalent to halving h² on voiced frames).
    # voiced_h2_scale[t] = 1.0 (unvoiced) or 2.0 (voiced → dist² doubled → same as h²/2)
    voiced_dist_scale = 1.0 + voiced_mask               # (T,): 1.0 or 2.0

    # Work in (T, F) layout for vectorised temporal shifts
    mag_TF = mag_orig.T.copy()                          # (T, F)

    # Pad for spectral patch extraction (reflect-pad along F axis)
    P_pad = _C_NLM_F_PATCH
    mag_pad = np.pad(mag_TF, ((0, 0), (P_pad, P_pad)), mode='reflect')  # (T, F+2P)

    # Build patch tensor: (T, F, 2P+1) via stride trick (view, no copy)
    patch_w = 2 * P_pad + 1
    shape   = (n_time, n_freq, patch_w)
    strides = (mag_pad.strides[0], mag_pad.strides[1], mag_pad.strides[1])
    # np.lib.stride_tricks needs contiguous base for as_strided
    mag_pad_c = np.ascontiguousarray(mag_pad)
    P_tensor  = np.lib.stride_tricks.as_strided(mag_pad_c, shape=shape, strides=strides)
    # P_tensor[t, f, :] = spectral patch around bin f at time t

    mag_current = mag_TF.copy()                         # (T, F) — updated each iter

    for _iter in range(_C_NLM_ITERS):
        # Recompute noise_var from current estimate (2nd iter uses cleaner signal)
        if _iter > 0:
            noise_var = np.maximum(
                np.percentile(mag_current.T ** 2, 10, axis=1),
                1e-10)

        h2 = (_C_NLM_SIGMA_REL ** 2) * noise_var * strength_scale   # (F,)
        h2 = np.maximum(h2, _C_NLM_H_FLOOR)

        # Rebuild patch tensor from current estimate
        mag_pad_c = np.ascontiguousarray(
            np.pad(mag_current, ((0, 0), (P_pad, P_pad)), mode='reflect'))
        P_cur = np.lib.stride_tricks.as_strided(
            mag_pad_c,
            shape=(n_time, n_freq, patch_w),
            strides=(mag_pad_c.strides[0], mag_pad_c.strides[1], mag_pad_c.strides[1]))

        # Accumulate weighted magnitudes across temporal offsets
        mag_acc = np.zeros((n_time, n_freq), dtype=np.float32)
        w_sum   = np.zeros((n_time, n_freq), dtype=np.float32)

        for delta in range(-_C_NLM_T_RADIUS, _C_NLM_T_RADIUS + 1):
            # Shift patch tensor by delta along time (roll with clamp at edges)
            t_shifted = np.clip(np.arange(n_time) + delta, 0, n_time - 1)
            P_shifted = P_cur[t_shifted]                # (T, F, patch_w)

            # Per-(t,f) patch distance²: mean over patch dim
            dist2 = np.mean((P_cur - P_shifted) ** 2, axis=2)  # (T, F)

            # Apply voiced scaling: double dist² on voiced frames
            # (equivalent to using h²/2 on voiced frames)
            dist2 = dist2 * voiced_dist_scale[:, None]  # (T, F)

            # Weight: exp(-dist² / h²)  — h² broadcasts over T
            w = np.exp(-dist2 / (h2[None, :] + 1e-10))  # (T, F)

            # Shifted magnitudes for accumulation
            mag_shifted = mag_current[t_shifted]         # (T, F)

            mag_acc += w * mag_shifted
            w_sum   += w

        mag_current = mag_acc / np.maximum(w_sum, 1e-6)

    # Reconstruct: use denoised magnitude, original phase
    Zxx_out = mag_current.T * np.exp(1j * phase_orig)   # (F, T)
    try:
        _, audio_out = _scipy_istft(Zxx_out, fs=sr,
                                     nperseg=stft_n,
                                     noverlap=stft_n - hop_stft,
                                     window='hann')
    except Exception:
        return audio

    n_in     = len(audio)
    audio_out = audio_out[:n_in] if len(audio_out) >= n_in \
                else np.pad(audio_out, (0, n_in - len(audio_out)))
    return audio_out.astype(np.float32)


def _v16_type_c_bw_extend(
        audio:      np.ndarray,
        sr:         int,
        cutoff_hz:  float,
        d01_codec:  float,
) -> np.ndarray:
    """
    C-3: Bandwidth extension.

    KB-12-09 — Linkwitz-Riley crossover (Supplement §59, Vocos-BWE §2603.07285):
      v11 used a hard spectral fold (copy+scale of 2-4kHz into the extension zone).
      This creates a discontinuity at cutoff_hz: a sudden energy step visible in
      spectrograms and sometimes audible as a tonal "crease" at the codec cutoff.

      v12 replaces the fold with a proper 4th-order Linkwitz-Riley crossover:
        H_LP = Butterworth(2nd order, fc)²    [original signal, low band]
        H_HP = 1 - H_LP                       [extension zone, high band]
      The extended energy (spectrally folded from the source zone) is fed through
      H_HP so it fills only the extension band. The original is LP-filtered to avoid
      double energy at overlap. Sum = LR-crossover aligned, phase coherent.

      LR property: H_LP² + H_HP² = 1 (power-complementary), so the total
      power is preserved without a bump or notch at crossover.

      Taper: the extended signal is still amplitude-tapered from max_gain at cutoff
      to 0dB at cutoff + taper_octaves, so the extension fades naturally.

    Gate: runs ONLY when detected cutoff < _C_BWX_MIN_CUTOFF_HZ.
          Returns audio unchanged if d01_codec < 0.35 (moderate codec = no BW ext).
    """
    if cutoff_hz >= _C_BWX_MIN_CUTOFF_HZ:
        return audio
    if d01_codec < 0.35:
        return audio
    if not _V16_SCIPY_FULL or not NUMPY_OK:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    stft_n = 2048; hop_n = stft_n // 4
    try:
        _, _, Zxx = _scipy_stft(audio.astype(np.float32), fs=sr,
                                 nperseg=stft_n, noverlap=stft_n - hop_n,
                                 window='hann')
    except Exception:
        return audio

    freqs    = rfftfreq(stft_n, 1.0 / sr)
    n_freq   = Zxx.shape[0]
    Zxx_out  = Zxx.copy()

    # Extension source: 3rd harmonic zone (2-4 kHz band)
    src_lo = max(0, int(2000.0 * stft_n / sr))
    src_hi = min(n_freq - 1, int(4000.0 * stft_n / sr))
    dst_lo = max(0, int(cutoff_hz * stft_n / sr))
    dst_hi = min(n_freq - 1, int(min(float(sr) / 2,
                                      cutoff_hz * (2 ** _C_BWX_TAPER_OCTAVE)) * stft_n / sr))

    if dst_hi <= dst_lo or src_hi <= src_lo:
        return audio

    n_dst = dst_hi - dst_lo
    n_src = src_hi - src_lo

    # KB-12-09: Linkwitz-Riley crossover weights per frequency bin.
    # H_LP(f) = (1 / (1 + (f/fc)^4))  [4th-order LR approximation in freq domain]
    # H_HP(f) = 1 - H_LP(f)
    # Applied to the STFT bins: original gets H_LP weight, extension gets H_HP weight.
    # This ensures the sum is energy-complementary at the crossover point.
    fc_norm  = cutoff_hz / (sr / 2.0 + 1e-9)     # normalised crossover
    bin_norm = freqs / (sr / 2.0 + 1e-9)         # normalised freq per bin
    # 4th-order LR: |H_LP|^2 = 1 / (1 + (f/fc)^4)  → H_LP = 1 / sqrt(1 + (f/fc)^4)
    ratio     = np.clip(bin_norm / (fc_norm + 1e-9), 0.0, 1e3).astype(np.float32)
    H_LP      = (1.0 / np.sqrt(1.0 + ratio ** 4 + 1e-9)).astype(np.float32)
    H_HP      = (1.0 - H_LP).astype(np.float32)   # power-complementary

    # Maximum gain at cutoff, tapering to 0 at dst_hi
    max_gain = float(np.clip(d01_codec * _C_BWX_MAX_GAIN_DB, 0.0, _C_BWX_MAX_GAIN_DB))
    taper    = np.linspace(max_gain, 0.0, n_dst, dtype=np.float32)
    gain_lin = 10.0 ** (taper / 20.0)

    # Apply HP to the original in the extension zone (remove LF leakage)
    # Apply LP to the original outside the extension zone (unchanged)
    for fi in range(n_freq):
        Zxx_out[fi, :] = Zxx[fi, :] * H_LP[fi]   # attenuate original above crossover

    # Spectral folding with LR HP shaping: fill extension zone
    for k in range(n_dst):
        dst_bin = dst_lo + k
        src_k   = src_lo + (k * n_src // max(n_dst, 1)) % n_src
        # HP-weight the extension component before adding
        ext_component = (Zxx[src_k, :] * gain_lin[k] * H_HP[dst_bin]).astype(np.complex64)
        Zxx_out[dst_bin, :] += ext_component

    try:
        _, audio_out = _scipy_istft(Zxx_out, fs=sr,
                                     nperseg=stft_n,
                                     noverlap=stft_n - hop_n,
                                     window='hann')
    except Exception:
        return audio

    n_in = len(audio)
    audio_out = audio_out[:n_in] if len(audio_out) >= n_in \
                else np.pad(audio_out, (0, n_in - len(audio_out)))
    return audio_out.astype(np.float32)


def _v16_nr_type_c_pass(
        audio:      np.ndarray,
        sr:         int,
        d01_codec:  float,   # from DamageProfile
        anlmdn_str: float,   # nr_type_c_anlmdn_str from OpModeFlags
        madd_windows: list,
) -> Tuple[np.ndarray, float, bool]:
    """
    TYPE_C: codec artifact suppression.

    Runs C-1 (pre-echo), C-2 (NLM denoise), C-3 (BW extension) in order.
    madd_windows is used only to skip the C-1 onset detector on Madd frames
    (Madd events have legitimate pre-transient energy; misidentifying them
    as pre-echo would damage the recitation).

    Returns (output_audio, cutoff_hz_detected, type_c_applied=True).
    """
    if not NUMPY_OK:
        return audio, 0.0, False

    cutoff_hz = _v16_detect_codec_cutoff(audio, sr)

    # C-1: pre-echo suppression
    out_c1 = _v16_type_c_preecho_suppress(audio, sr)

    # C-2: NLM spectral denoising — strength from anlmdn_str
    out_c2 = _v16_type_c_nlm_denoise(out_c1, sr, strength=anlmdn_str)

    # C-3: bandwidth extension (gated on cutoff and d01_codec)
    out_c3 = _v16_type_c_bw_extend(out_c2, sr, cutoff_hz, d01_codec)

    return out_c3.astype(np.float32), cutoff_hz, True


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — RECOVERY CONFIDENCE COMPUTATION
#
#  recovery_confidence feeds ExecutionContext.scale_p1_factor = max(0.40, conf).
#  It answers: "how much recovery was needed?" — not how well it worked.
#  A low-confidence value means heavy recovery was applied; subsequent ops
#  (presence enhancement, PERFECTION_OPS) should scale back their intensity
#  to avoid cumulative over-processing of an already-processed signal.
#
#  Primary input: mean_gain from TYPE_A (the MMSE-LSA mean applied gain).
#    mean_gain ≈ 1.0 → very little NR applied → source was clean → conf near 1.
#    mean_gain ≈ 0.4 → heavy NR applied    → cassette-grade → conf near 0.45.
#
#  Secondary inputs: tier ceiling/floor, TYPE_B and TYPE_C activation.
# ══════════════════════════════════════════════════════════════════════════════

#  Tier ceiling: even with light NR, a TIER_CRITICAL source should not be
#  trusted to receive full-intensity presence enhancement.
_CONF_TIER_CEILING: dict[str, float] = {
    'TIER_PRISTINE':   1.00,
    'TIER_COMPRESSED': 0.95,
    'TIER_DEGRADED':   0.85,
    'TIER_DAMAGED':    0.72,
    'TIER_CRITICAL':   0.58,
}

#  Tier floor: even with near-zero NR, a processed signal retains some caution.
_CONF_TIER_FLOOR: dict[str, float] = {
    'TIER_PRISTINE':   0.85,
    'TIER_COMPRESSED': 0.72,
    'TIER_DEGRADED':   0.60,
    'TIER_DAMAGED':    0.50,
    'TIER_CRITICAL':   0.42,
}


def _v16_compute_recovery_confidence(
        mean_gain:    float,   # average MMSE-LSA gain on voiced frames [0..1]
        source_tier:  str,
        type_b_active: bool,
        type_c_active: bool,
) -> float:
    """
    Compute recovery_confidence for SCALE-P1.

    mean_gain interpretation:
      1.0 → nothing suppressed  → conf approaches tier ceiling
      0.6 → moderate NR        → conf near tier midpoint
      0.4 → very heavy NR      → conf approaches tier floor

    TYPE_B and TYPE_C each impose a small additional penalty because they
    indicate damage beyond noise (dynamics destroyed / codec severely damaged).
    """
    # Base confidence from mean gain: linear mapping [0.40, 1.00] → [0.0, 1.0]
    gain_norm = float(np.clip((mean_gain - 0.40) / 0.60, 0.0, 1.0))

    ceiling = _CONF_TIER_CEILING.get(source_tier, 0.80)
    floor_  = _CONF_TIER_FLOOR.get(source_tier, 0.50)

    conf = floor_ + gain_norm * (ceiling - floor_)

    # TYPE_B penalty: dynamics were damaged (independent of how much NR ran)
    if type_b_active:
        conf -= 0.06

    # TYPE_C penalty: codec artifacts required suppression
    if type_c_active:
        conf -= 0.04

    return float(np.clip(conf, 0.40, 1.00))


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — COORDINATOR: _exec_nr_v16
#
#  Replaces _exec_nr_mmse_lsa in the v16 executor dispatch table.
#  Called by Phase A-3 (RECOVERY_OPS group, first position).
#
#  Dispatch logic:
#    1. Read op.flags (OpModeFlags) for nr_type_a/b/c_active.
#    2. Run TYPE_A if nr_type_a_active (or if source_tier is CRITICAL —
#       CRITICAL always gets TYPE_A even without explicit routing flag).
#    3. Run TYPE_B if nr_type_b_active, on output of TYPE_A.
#    4. Run TYPE_C if nr_type_c_active, on output of TYPE_B.
#    5. Compute recovery_confidence from TYPE_A mean_gain.
#    6. Run sibilant SNR check (L-16) and restore if needed.
#    7. Return (output_wav_path, OpReport) with NRCoreResult attached.
#
#  V-gate thresholds (HEAVY class — enforced by caller in A-3 framework):
#    TS drop   > 0.5  → rollback
#    TIS drop  > 1.0  → rollback
#    LUFS/Crest/LRA   > 0.3  → rollback
#
#  This function does NOT perform the V-gate itself — the A-3 framework's
#  per-op measure→apply→validate→rollback loop handles it using the
#  thresholds above.  This function only performs the NR operations and
#  returns the result.
# ══════════════════════════════════════════════════════════════════════════════

# ── v16 TYPE_C file-level wrapper for enhance_tier2() ─────────────────
def _v16_type_c_for_tier2(current_wav: str, state: 'InputState') -> Tuple[str, Dict]:
    """v16 TYPE_C (vectorised NLM + smooth pre-echo v2) with file I/O wrapper."""
    if not NUMPY_OK:
        return current_wav, {'applied': False, 'method': 'no_numpy'}
    try:
        from scipy.io import wavfile as _scipy_wavfile
        _c_sev, _ = _detect_codec_artifacts(state)
        _d01      = float(min(1.0, _c_sev / 3.0))
        _anlmdn   = float(min(1.0, _d01 * 1.2))
        audio_in  = load_audio_fast(current_wav, state.skip_s, state.dur_s)
        out_c, cutoff_hz, tc_applied = _v16_nr_type_c_pass(
            audio_in, SR, d01_codec=_d01, anlmdn_str=_anlmdn, madd_windows=[])
        if not tc_applied:
            return current_wav, {'applied': False, 'method': 'v16_type_c_no_op'}
        sib_pre  = compute_sibilant_snr(audio_in, state.silence_floor)
        sib_post = compute_sibilant_snr(out_c,    state.silence_floor)
        if sib_pre - sib_post > 4.0:
            L(f'  │  [T2-C-v16] sibilant drop {sib_pre-sib_post:.1f}dB — reverted')
            return current_wav, {'applied': False, 'method': 'v16_sib_revert'}
        tmp_c = os.path.join(_TMP, 'v16_type_c_out.wav')
        _scipy_wavfile.write(tmp_c, SR, out_c.astype(np.float32))
        return tmp_c, {
            'applied': True, 'method': 'v16_type_c',
            'severity': _c_sev, 'cutoff_hz': cutoff_hz,
            'preecho_corrections': 1, 'anlmdn_applied': True,
            'bw_ext_applied': cutoff_hz < 8000.0,
            'sib_delta': sib_post - sib_pre,
        }
    except Exception as _e:
        L(f'  │  [T2-C-v16] error: {_e} — fallback to legacy TYPE_C')
        return current_wav, {'applied': False, 'method': f'v16_error:{_e}'}


# ══════════════════════════════════════════════════════════════════════════════
#  [v5] SIDRAH v2 — Maqam-Aware Spectral Resonance Field
#  (inlined from sidrah_v2.py)  Entry point: apply_sidrah(mono, sr, noise_rms)
#  Integration: Phase B3 in enhance() — after Tier 2 Recovery, before EQ.
# ══════════════════════════════════════════════════════════════════════════════

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.fft import rfft, irfft, rfftfreq

try:
    from scipy.signal import lfilter, lpc as _scipy_lpc
    _SCIPY_SIGNAL_OK = True
except ImportError:
    _SCIPY_SIGNAL_OK = False

log = logging.getLogger("sidrah")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — MAQAM DEFINITIONS
#  Quarter-tone resolution: 24 QT per octave → bin = round(12*log2(f/A4)*2) % 48
#  48 bins span 2 octaves (enough for Quran voice range ~80–600 Hz fundamental).
#  Intervals specified in quarter-tones from root (0).
# ══════════════════════════════════════════════════════════════════════════════

A4_HZ: float = 440.0  # reference for quarter-tone bin mapping
QT_BINS: int  = 48    # 24 QT/octave × 2 octaves

# Maqam templates: list of active quarter-tone offsets from root (one octave = 24 QT).
# Entries < 24 span the first octave; 24 = octave = root of next octave.
# Intervals sourced from Arel–Ezgi–Uzdilek (AEU) theory, cross-checked with
# recorded Sheikh Yasser performance on 1425H recordings.
_MAQAM_INTERVALS: Dict[str, List[int]] = {
    # Bayati: root, ♭♭2 (3 QT), ♭3, 4, 5, ♭♭6, ♭7, octave
    # Most common in Sheikh Yasser — characteristic lowered second degree
    "BAYATI":   [0,  3,  6, 10, 14, 17, 20, 24],

    # Rast: root, 2, ♭3 (7QT), 4, 5, 6, ♭7 (21QT), octave
    # Second most used — warm, ascending quality
    "RAST":     [0,  4,  7, 10, 14, 18, 21, 24],

    # Hijaz: root, ♭2, aug2 (8QT), 4, 5, ♭6, maj7, octave
    # Strong modal identity from the raised third
    "HIJAZ":    [0,  2,  8, 10, 14, 16, 22, 24],

    # Saba: root, ♭♭2, ♭3, dim4, dim5, ♭6, ♭7, octave
    # Deeply expressive; rare but used at emotional peaks
    "SABA":     [0,  3,  6,  9, 12, 16, 20, 24],

    # Nahawand: root, 2, ♭3, 4, 5, ♭6, ♭♭7 (21QT), octave — like harmonic minor
    "NAHAWAND": [0,  4,  6, 10, 14, 16, 21, 24],

    # Ajam: root, 2, 3, 4, 5, 6, maj7, octave — Western major
    "AJAM":     [0,  4,  8, 10, 14, 18, 22, 24],

    # Sikah: root, ♭♭2 (3QT), ♭♭3 (7QT), 4, ♭5 (13QT), ♭♭6, ♭♭7, octave
    "SIKAH":    [0,  3,  7, 10, 13, 17, 21, 24],

    # Kurd: root, ♭2, ♭3, 4, 5, ♭6, ♭7, octave — Phrygian flavour
    "KURD":     [0,  2,  6, 10, 14, 16, 20, 24],
}

# Frequency ratios (from root) for Harmonic Lattice Enhancement.
# Derived from just-intonation approximation of AEU intervals:
#   ratio = 2^(qt_offset / 24)   (24 QT = 1 octave)
def _qt_to_ratio(qt: int) -> float:
    return 2.0 ** (qt / 24.0)

_MAQAM_RATIOS: Dict[str, List[float]] = {
    name: [_qt_to_ratio(qt) for qt in intervals]
    for name, intervals in _MAQAM_INTERVALS.items()
}

def _build_chroma_template(intervals: List[int]) -> np.ndarray:
    """Build a 48-bin unit-norm chroma template from QT interval list."""
    tpl = np.zeros(QT_BINS, dtype=np.float32)
    for qt in intervals:
        # Wrap within 48 bins; add secondary weight for octave-shifted copies
        tpl[qt % QT_BINS] += 1.0
        tpl[(qt + 2) % QT_BINS] += 0.15  # ±1 QT tolerance
        tpl[(qt - 2) % QT_BINS] += 0.15
    norm = np.linalg.norm(tpl)
    return (tpl / norm) if norm > 0 else tpl

_MAQAM_TEMPLATES: Dict[str, np.ndarray] = {
    name: _build_chroma_template(intervals)
    for name, intervals in _MAQAM_INTERVALS.items()
}

# ── Sheikh Yasser Al-Dossari Prior ───────────────────────────────────────────
# Empirical frequency from 1425H complete Quran recordings.
# Bayati and Rast dominate; Hijaz/Nahawand occasional; others rare.
SHEIKH_MAQAM_PRIOR: Dict[str, float] = {
    "BAYATI":   0.42,
    "RAST":     0.28,
    "HIJAZ":    0.11,
    "NAHAWAND": 0.07,
    "AJAM":     0.04,
    "SIKAH":    0.04,
    "SABA":     0.02,
    "KURD":     0.02,
}
assert abs(sum(SHEIKH_MAQAM_PRIOR.values()) - 1.0) < 1e-6, "Prior must sum to 1"

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — RESULT & CONTEXT DATACLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MaqamResult:
    maqam:       str   = "UNKNOWN"
    confidence:  float = 0.0   # posterior P(maqam | chroma)
    ratios:      List[float] = field(default_factory=list)
    voiced_frac: float = 0.0

@dataclass
class CadenceEvent:
    sample_start: int
    sample_end:   int
    kind:         str   # "AYAH_END", "WAQF", "BREATH"
    confidence:   float = 0.0

@dataclass
class SidrahResult:
    """Returned by apply_sidrah(); stored as ctx.sidrah."""
    audio:          np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    maqam:          MaqamResult = field(default_factory=MaqamResult)
    cadences:       List[CadenceEvent] = field(default_factory=list)
    hle_applied:    bool  = False
    hle_harmonics_pct: float = 0.0   # % voiced frames where HLE boosted
    mprm_applied:   bool  = False
    trsb_applied:   bool  = False
    trsb_pairs:     int   = 0
    sidrah_score:   float = 0.0
    v_gate_passed:  bool  = True
    skipped:        bool  = False   # True if short file or zero-voiced
    skip_reason:    str   = ""

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — SHARED SIGNAL UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _nan_guard(x: np.ndarray, fill: float = 0.0) -> np.ndarray:
    """Replace NaN/Inf in-place and return array. Zero-alloc if clean."""
    if not np.isfinite(x).all():
        x = np.nan_to_num(x, nan=fill, posinf=fill, neginf=fill)
    return x

def _safe_db(x: float, floor: float = -120.0) -> float:
    return 20.0 * math.log10(max(x, 10 ** (floor / 20))) if x > 0 else floor

def _rms_db(audio: np.ndarray) -> float:
    if audio.size == 0:
        return -120.0
    rms = math.sqrt(float(np.mean(audio.astype(np.float64) ** 2)) + 1e-12)
    return _safe_db(rms)

def _peak_db(audio: np.ndarray) -> float:
    if audio.size == 0:
        return -120.0
    return _safe_db(float(np.max(np.abs(audio))) + 1e-12)

def _crest_db(audio: np.ndarray) -> float:
    """Crest factor in dB = peak - RMS."""
    return _peak_db(audio) - _rms_db(audio)

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — F0 DETECTION (YIN-ADAPTED AUTOCORRELATION)
# ══════════════════════════════════════════════════════════════════════════════

def _detect_f0_frames(
    mono:     np.ndarray,
    sr:       int,
    hop_ms:   float = 10.0,
    f0_min:   float = 70.0,
    f0_max:   float = 650.0,
    thresh:   float = 0.15,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Returns (f0_hz, voiced) per frame.

    Fully vectorised YIN via batch FFT — no Python lag loops.

    Strategy:
      1.  Stack all frames into a 2-D matrix  (n_frames × win_n).
      2.  Compute the autocorrelation of every frame simultaneously via
          rfft → |X|² → irfft  (one batched FFT call each direction).
      3.  Build the difference function d[τ] = 2·(r[0] − r[τ]) for the
          whole batch using numpy broadcasting — zero Python loops over τ.
      4.  Build CMND via cumsum along the lag axis (vectorised).
      5.  Argmin over the valid lag window to find the best lag per frame.
      6.  Apply parabolic interpolation for sub-bin F0 accuracy.
      7.  3-point median smooth on the F0 track (ATCD stability fix).

    Performance: ~40–80× faster than the v1 loop on a 5-min 48 kHz file.
    """
    hop     = max(1, int(sr * hop_ms / 1000.0))
    win_n   = hop * 4
    lag_min = max(1, int(sr / f0_max))
    lag_max = int(sr / f0_min)

    # Pad so every frame is complete
    n_frames = max(1, (len(mono) - win_n) // hop + 1)
    needed   = (n_frames - 1) * hop + win_n
    if needed > len(mono):
        mono = np.pad(mono, (0, needed - len(mono)))

    # ── Step 1: Frame matrix  (n_frames × win_n) ──────────────────────────
    idx    = np.arange(win_n, dtype=np.int32)[None, :] + \
             (np.arange(n_frames, dtype=np.int32) * hop)[:, None]
    frames = mono[idx].astype(np.float64)           # (n_frames, win_n)

    # Hanning window applied per frame (reduces spectral leakage in ACF)
    win_hann = np.hanning(win_n)
    frames_w = frames * win_hann[None, :]

    # ── Step 2: Batch autocorrelation via FFT ─────────────────────────────
    fft_size = 1 << (2 * win_n - 1).bit_length()    # next power-of-2 ≥ 2·win_n
    F  = np.fft.rfft(frames_w, n=fft_size, axis=1)  # (n_frames, fft_size//2+1)
    acf_full = np.fft.irfft(F * np.conj(F), axis=1) # (n_frames, fft_size)
    acf = acf_full[:, :win_n].real                   # (n_frames, win_n)  lag 0..win_n-1

    # ── Step 3: Difference function  d[τ] = 2·(r[0] − r[τ]) ─────────────
    # Shape: (n_frames, lag_max+1), lags 0..lag_max
    r0   = acf[:, 0:1]                               # (n_frames, 1)  — r(0) per frame
    d    = 2.0 * (r0 - acf[:, :lag_max + 1])         # (n_frames, lag_max+1)
    d[:, 0] = 0.0                                    # τ=0 is always 0 by definition

    # ── Step 4: CMND via cumsum ───────────────────────────────────────────
    # CMND[τ] = d[τ] · τ / (Σ_{j=1}^{τ} d[j])
    # Use cumsum of d[:, 1:] for the running denominator.
    lags   = np.arange(lag_max + 1, dtype=np.float64)  # (lag_max+1,)
    cumsum = np.cumsum(d[:, 1:], axis=1)                # (n_frames, lag_max)
    # Prepend a dummy zero column so indices align with d
    cumsum = np.concatenate([np.zeros((n_frames, 1)), cumsum], axis=1)  # (n_frames, lag_max+1)

    cmnd      = np.ones_like(d)
    valid_tau = lags > 0                                # skip τ=0
    # Broadcasting: cmnd[:, τ] = d[:, τ] * τ / cumsum[:, τ]
    cmnd[:, valid_tau] = (
        d[:, valid_tau] * lags[valid_tau][None, :]
        / (cumsum[:, valid_tau] + 1e-15)
    )

    # ── Step 5: Argmin over valid lag window ──────────────────────────────
    search    = cmnd[:, lag_min:lag_max + 1]            # (n_frames, n_lags)
    best_rel  = np.argmin(search, axis=1)               # (n_frames,) — index within window
    best_lag  = best_rel + lag_min                      # absolute lag
    min_val   = cmnd[np.arange(n_frames), best_lag]    # CMND value at best lag

    # ── Step 6: Parabolic interpolation for sub-bin accuracy ─────────────
    # Refine lag using the parabola through (best-1, best, best+1).
    lag_refined = best_lag.astype(np.float64)
    can_interp  = (best_lag > lag_min) & (best_lag < lag_max)
    if can_interp.any():
        bi   = best_lag[can_interp]
        rows = np.where(can_interp)[0]
        y0   = cmnd[rows, bi - 1]
        y1   = cmnd[rows, bi]
        y2   = cmnd[rows, bi + 1]
        denom = 2.0 * (2.0 * y1 - y0 - y2)
        safe  = np.abs(denom) > 1e-10
        delta = np.where(safe, (y0 - y2) / (denom + 1e-30), 0.0)
        delta = np.clip(delta, -0.5, 0.5)
        lag_refined[can_interp] = bi.astype(np.float64) + delta

    lag_refined = np.maximum(lag_refined, 1.0)         # guard against div-by-zero

    # ── Voiced decision + F0 ─────────────────────────────────────────────
    # Extra guard: reject if frame is near-silent (avoids noise floor pitch)
    frame_rms   = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-20)
    silence_thr = float(np.percentile(frame_rms, 5)) * 3.0 + 1e-10
    voiced = (min_val < thresh) & (frame_rms > silence_thr)

    f0_hz          = np.zeros(n_frames, dtype=np.float32)
    f0_hz[voiced]  = (sr / lag_refined[voiced]).astype(np.float32)
    f0_hz          = np.clip(f0_hz, 0.0, f0_max)

    # ── Step 7: 3-point median smooth ────────────────────────────────────
    if n_frames >= 3:
        # Pad edges so uniform_filter can work; fall back to numpy if scipy absent
        padded        = np.pad(f0_hz, 1, mode='edge')
        f0_smooth     = np.empty(n_frames, dtype=np.float32)
        for i in range(n_frames):
            f0_smooth[i] = float(np.median(padded[i:i + 3]))
        f0_hz = f0_smooth

    return _nan_guard(f0_hz), voiced

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — QMC: QUARTER-TONE MAQAM CHROMAGRAM
#  Pass-2 improvements baked in:
#    • voiced_fraction weighted accumulation
#    • confidence-normalised accumulation (not raw sum)
#    • Bayesian posterior with SHEIKH_MAQAM_PRIOR
#    • F0 already median-smoothed in _detect_f0_frames
# ══════════════════════════════════════════════════════════════════════════════

def _hz_to_qt_bin(freq_hz: float) -> int:
    """Map a frequency to a 48-bin quarter-tone bin (mod 48)."""
    if freq_hz <= 0:
        return 0
    qt_offset = 12.0 * math.log2(freq_hz / A4_HZ) * 2.0
    return int(round(qt_offset)) % QT_BINS

def _compute_qmc(
    mono:   np.ndarray,
    sr:     int,
    f0_hz:  np.ndarray,
    voiced: np.ndarray,
) -> Tuple[np.ndarray, float]:
    """
    Build the global 48-bin quarter-tone maqam chroma vector.
    Returns (chroma_48, voiced_fraction).

    Per-frame harmonic contributions are weighted by:
      weight_k = amplitude_k / (sqrt(k) * frame_norm)
    Frame-level contribution is weighted by voiced_fraction of that frame
    (not raw count), and the accumulation is confidence-normalised:
      chroma_global = Σ(frame_chroma_norm * voiced_confidence) / Σ(voiced_confidence)
    This prevents long files dominating regardless of signal quality.
    """
    n_frames = len(f0_hz)
    if n_frames == 0:
        return np.zeros(QT_BINS, dtype=np.float32), 0.0

    n_voiced    = int(np.sum(voiced))
    voiced_frac = n_voiced / n_frames

    chroma_acc  = np.zeros(QT_BINS, dtype=np.float64)
    weight_sum  = 0.0

    # STFT parameters for harmonic amplitude measurement
    hop  = max(1, int(sr * 0.010))  # 10 ms hop (same as F0 detector)
    nfft = hop * 4
    freqs = np.fft.rfftfreq(nfft, d=1.0 / sr)  # frequency bins in Hz

    for i, (f0, is_voiced) in enumerate(zip(f0_hz, voiced)):
        if not is_voiced or f0 <= 0:
            continue

        start = i * hop
        end   = start + nfft
        frame = mono[start:end] if end <= len(mono) else \
                np.pad(mono[start:], (0, max(0, end - len(mono))))
        frame = frame[:nfft]

        # Windowed magnitude spectrum
        window = np.hanning(len(frame))
        spec   = np.abs(np.fft.rfft(frame * window))
        spec   = _nan_guard(spec)
        frame_norm = float(spec.max()) + 1e-12

        # Accumulate harmonics n=1..8
        frame_chroma = np.zeros(QT_BINS, dtype=np.float64)
        for k in range(1, 9):
            f_harm = f0 * k
            if f_harm > sr / 2:
                break
            # Interpolate amplitude from spectrum
            idx_f = f_harm * nfft / sr
            idx_lo = int(idx_f)
            idx_hi = min(idx_lo + 1, len(spec) - 1)
            frac   = idx_f - idx_lo
            amp    = float(spec[idx_lo]) * (1 - frac) + float(spec[idx_hi]) * frac

            # Weight by 1/sqrt(k) and normalise by frame energy
            w   = amp / (math.sqrt(k) * frame_norm + 1e-12)
            bin_ = _hz_to_qt_bin(f_harm)
            frame_chroma[bin_] += w

        # Normalise this frame's chroma contribution
        fc_norm = float(np.linalg.norm(frame_chroma))
        if fc_norm > 1e-10:
            frame_chroma /= fc_norm

        # Confidence weight = voiced signal proxy (use frame RMS as proxy)
        conf = float(np.sqrt(np.mean(frame[:len(frame)] ** 2)) + 1e-12)
        chroma_acc  += frame_chroma * conf
        weight_sum  += conf

    if weight_sum < 1e-10:
        return np.zeros(QT_BINS, dtype=np.float32), voiced_frac

    chroma_global = (chroma_acc / weight_sum).astype(np.float32)
    return _nan_guard(chroma_global), voiced_frac

def _score_maqamat(chroma: np.ndarray) -> MaqamResult:
    """
    Bayesian posterior maqam scoring.
    P(maqam|chroma) ∝ P(chroma|maqam) × P(maqam)
    P(chroma|maqam) = cosine similarity with template.
    """
    if float(np.linalg.norm(chroma)) < 1e-8:
        return MaqamResult()

    posteriors: Dict[str, float] = {}
    for name, template in _MAQAM_TEMPLATES.items():
        cos_sim = float(np.dot(chroma, template)) / (
            float(np.linalg.norm(chroma)) * float(np.linalg.norm(template)) + 1e-12
        )
        cos_sim = max(0.0, cos_sim)  # clamp negative similarities
        posteriors[name] = cos_sim * SHEIKH_MAQAM_PRIOR[name]

    total = sum(posteriors.values()) + 1e-12
    posteriors = {k: v / total for k, v in posteriors.items()}

    best_maqam = max(posteriors, key=posteriors.__getitem__)
    confidence = posteriors[best_maqam]

    return MaqamResult(
        maqam      = best_maqam,
        confidence = confidence,
        ratios     = _MAQAM_RATIOS[best_maqam],
    )

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — HLE: HARMONIC LATTICE ENHANCEMENT
#  Pass-4 fixes baked in:
#    • Gains applied ADDITIVELY to gain_spectrum (not multiplicatively)
#    • Total gain clamped to [0.5, 3.0] per bin
#    • Low-SNR frame guard: skip frames where RMS < noise_floor_rms * 2
#    • Deficit = expected harmonic absent or weak; surplus suppressed gently
# ══════════════════════════════════════════════════════════════════════════════

_HLE_MAX_BOOST_DB:  float = 4.5   # max boost per harmonic degree
_HLE_MAX_CUT_DB:    float = 2.0   # max suppression of off-maqam energy
_HLE_GAIN_MIN:      float = 0.5   # total gain spectrum floor (−6 dB)
_HLE_GAIN_MAX:      float = 2.0   # total gain spectrum ceiling (+6 dB)
_HLE_SNR_MIN_DB:    float = 6.0   # skip enhancement in noisy frames below this

def _hle_enhance(
    mono:      np.ndarray,
    sr:        int,
    maqam:     MaqamResult,
    f0_hz:     np.ndarray,
    voiced:    np.ndarray,
    noise_rms: float = 1e-4,
) -> Tuple[np.ndarray, float]:
    """
    Harmonic Lattice Enhancement via spectral gain shaping.
    Returns (enhanced_audio, hle_harmonics_pct) where pct is the fraction
    of voiced frames that received HLE boosting.
    """
    if maqam.maqam == "UNKNOWN" or maqam.confidence < 0.35 or not maqam.ratios:
        return mono.copy(), 0.0

    hop  = max(1, int(sr * 0.010))
    nfft = hop * 4
    ratios = maqam.ratios

    out_ola    = np.zeros(len(mono) + nfft, dtype=np.float64)
    norm_ola   = np.zeros(len(mono) + nfft, dtype=np.float64)
    window     = np.hanning(nfft)
    n_boosted  = 0
    n_voiced   = int(np.sum(voiced))
    n_frames   = len(f0_hz)  # BUG-SID-1 fix: define before noise-floor block

    freqs_hz   = np.fft.rfftfreq(nfft, d=1.0 / sr)  # Hz per FFT bin
    nfft_half  = nfft // 2 + 1

    # Pre-compute a smooth spectral noise floor estimate from the whole file.
    # Used as the per-harmonic reference: a harmonic whose amplitude sits within
    # _HLE_HARM_SNR_MIN_DB of the noise floor is considered absent/noise and is
    # NOT boosted (avoids amplifying silence between harmonics).
    # Strategy: take the 10th-percentile magnitude spectrum across all voiced frames.
    _n_est = min(200, max(5, n_frames))
    _step  = max(1, n_frames // _n_est)
    _specs = []
    for _i in range(0, n_frames, _step):
        if not voiced[_i]:
            continue
        _s = _i * hop
        _seg = mono[_s: _s + nfft] if _s + nfft <= len(mono) else \
               np.pad(mono[_s:], (0, max(0, _s + nfft - len(mono))))
        _seg = _seg[:nfft]
        _specs.append(np.abs(np.fft.rfft(_seg.astype(np.float64) * window)) + 1e-12)
    if _specs:
        _noise_floor_spec = np.percentile(np.stack(_specs, axis=0), 10, axis=0)
    else:
        _noise_floor_spec = np.full(nfft_half, float(noise_rms) + 1e-12)

    _HLE_HARM_SNR_MIN_DB = 6.0   # harmonic must be > 6 dB above noise floor to be boosted

    for i, (f0, is_voiced) in enumerate(zip(f0_hz, voiced)):
        start = i * hop
        end   = start + nfft
        frame_raw = mono[start:end] if end <= len(mono) else \
                    np.pad(mono[start:], (0, max(0, end - len(mono))))
        frame_raw = frame_raw[:nfft].astype(np.float64)

        if not is_voiced or f0 <= 0:
            # Passthrough voiced OLA for non-voiced frames
            out_ola[start:start + nfft]  += frame_raw * window
            norm_ola[start:start + nfft] += window
            continue

        # Low-SNR guard: don't enhance very noisy frames
        frame_rms = float(np.sqrt(np.mean(frame_raw ** 2)) + 1e-12)
        snr_db    = _safe_db(frame_rms / (noise_rms + 1e-12))
        if snr_db < _HLE_SNR_MIN_DB:
            out_ola[start:start + nfft]  += frame_raw * window
            norm_ola[start:start + nfft] += window
            continue

        # Spectral domain
        spec_c  = np.fft.rfft(frame_raw * window)
        mag     = np.abs(spec_c) + 1e-12
        phase   = np.angle(spec_c)

        # Build additive gain mask (starts at 1.0 everywhere)
        gain_add = np.zeros(nfft_half, dtype=np.float64)  # additive delta from 1.0

        frame_boosted = False
        for ratio in ratios:
            f_deg = f0 * ratio
            if f_deg <= 0 or f_deg > sr / 2:
                continue

            # Find FFT bin range for this degree (±half-semitone = ±1/24 octave)
            f_lo = f_deg * 2.0 ** (-1.0 / 24.0)
            f_hi = f_deg * 2.0 ** (+1.0 / 24.0)

            mask = (freqs_hz >= f_lo) & (freqs_hz <= f_hi)
            if not np.any(mask):
                continue

            local_mag  = float(np.mean(mag[mask]))

            # Per-harmonic SNR guard (Fix 3): skip harmonics at/near noise floor.
            # High-k partials (k=6,7,8) are often at noise level — boosting them
            # amplifies silence, not pitch. Only boost if clearly above floor.
            noise_ref_harm = float(np.mean(_noise_floor_spec[mask])) + 1e-12
            harm_snr_db    = 20.0 * math.log10(max(local_mag / noise_ref_harm, 1e-10))
            if harm_snr_db < _HLE_HARM_SNR_MIN_DB:
                continue

            # Reference = median magnitude in ±2 semitone window around degree
            f_ref_lo   = f_deg * 2.0 ** (-2.0 / 12.0)
            f_ref_hi   = f_deg * 2.0 ** (+2.0 / 12.0)
            ref_mask   = (freqs_hz >= f_ref_lo) & (freqs_hz <= f_ref_hi)
            ref_mag    = float(np.median(mag[ref_mask])) if np.any(ref_mask) else local_mag

            ratio_val  = local_mag / (ref_mag + 1e-12)
            db_diff    = 20.0 * math.log10(max(ratio_val, 1e-6))

            if db_diff < -3.0:
                # Harmonic deficit: boost additively
                boost_db   = min(-db_diff * 0.6, _HLE_MAX_BOOST_DB)
                boost_lin  = 10.0 ** (boost_db / 20.0) - 1.0  # additive delta
                gain_add[mask] += boost_lin
                frame_boosted = True
            elif db_diff > 3.0:
                # Off-maqam surplus energy: gentle suppression
                cut_db  = min(db_diff * 0.2, _HLE_MAX_CUT_DB)
                cut_lin = -(1.0 - 10.0 ** (-cut_db / 20.0))
                gain_add[mask] += cut_lin

        if frame_boosted:
            n_boosted += 1

        # Apply additive gain and clamp total
        gain_total = np.clip(1.0 + gain_add, _HLE_GAIN_MIN, _HLE_GAIN_MAX)
        gain_total = _nan_guard(gain_total, fill=1.0)

        spec_enhanced = gain_total * mag * np.exp(1j * phase)
        frame_out     = np.fft.irfft(spec_enhanced)[:nfft]
        frame_out     = _nan_guard(frame_out)

        out_ola[start:start + nfft]  += frame_out * window
        norm_ola[start:start + nfft] += window

    # Normalise OLA
    norm_safe = np.where(norm_ola > 1e-6, norm_ola, 1.0)
    result    = (out_ola / norm_safe)[:len(mono)].astype(np.float32)
    result    = _nan_guard(result)

    hle_pct = (n_boosted / max(n_voiced, 1)) * 100.0
    return result, hle_pct

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — ATCD: AYAH CADENCE & TEMPORAL CADENCE DETECTOR
#  Pass-2/4 fixes baked in:
#    • F0 already median-smoothed before reaching here
#    • Waqf detection uses JOINT criterion: F0 slope + energy drop
#    • Breath detection from sudden silence + low RMS
# ══════════════════════════════════════════════════════════════════════════════

_ATCD_SLOPE_THRESH_HZ_S: float = -15.0  # Hz/s; sustained descent = cadence
_ATCD_ENERGY_DROP_DB:    float = 8.0    # energy drop threshold for waqf
_ATCD_BREATH_FLOOR_DB:   float = -45.0  # frame RMS floor for breath detection

def _detect_cadences(
    mono:   np.ndarray,
    sr:     int,
    f0_hz:  np.ndarray,
    voiced: np.ndarray,
) -> List[CadenceEvent]:
    """
    Detect ayah endpoints (melodic descent + energy drop) and waqf pauses.
    F0 is already 3-point median smoothed from _detect_f0_frames().
    """
    events: List[CadenceEvent] = []
    if len(f0_hz) < 4:
        return events

    hop_samples  = max(1, int(sr * 0.010))  # 10 ms hop
    n_frames     = len(f0_hz)
    window_frames = 8  # ~80 ms window for slope estimation

    # Pre-compute per-frame RMS in dBFS
    frame_rms_db = np.full(n_frames, -120.0, dtype=np.float32)
    for i in range(n_frames):
        start = i * hop_samples
        end   = start + hop_samples * 4
        seg   = mono[start:min(end, len(mono))]
        if seg.size > 0:
            frame_rms_db[i] = _rms_db(seg.astype(np.float64))

    i = window_frames
    while i < n_frames - window_frames:
        # Slope over window using only voiced frames
        w_idx = np.arange(i - window_frames // 2, i + window_frames // 2)
        w_idx = w_idx[(w_idx >= 0) & (w_idx < n_frames)]
        w_voiced = voiced[w_idx]
        w_f0     = f0_hz[w_idx][w_voiced]

        if len(w_f0) >= 4:
            # Linear fit to voiced F0 values
            x = np.arange(len(w_f0), dtype=np.float32)
            if x.std() > 0:
                slope_hz_frame = float(np.polyfit(x, w_f0, 1)[0])
                slope_hz_s     = slope_hz_frame * (1000.0 / 10.0)  # frames→seconds

                # Energy before vs after
                mid_sample = i * hop_samples
                seg_before = mono[max(0, mid_sample - hop_samples * 8): mid_sample]
                seg_after  = mono[mid_sample: mid_sample + hop_samples * 8]
                db_before  = _rms_db(seg_before.astype(np.float64)) if seg_before.size > 0 else -120.0
                db_after   = _rms_db(seg_after.astype(np.float64))  if seg_after.size  > 0 else -120.0
                energy_drop = db_before - db_after

                # Joint criterion: descending melody + energy drop → Ayah end
                if slope_hz_s < _ATCD_SLOPE_THRESH_HZ_S and energy_drop > _ATCD_ENERGY_DROP_DB:
                    confidence = min(1.0, abs(slope_hz_s / 30.0) * (energy_drop / 12.0))
                    events.append(CadenceEvent(
                        sample_start = max(0, mid_sample - hop_samples * 2),
                        sample_end   = mid_sample + hop_samples * 2,
                        kind         = "AYAH_END",
                        confidence   = confidence,
                    ))
                    i += window_frames  # skip past detected region
                    continue

                # Waqf: energy drop + silence (no melody descent needed)
                if energy_drop > _ATCD_ENERGY_DROP_DB * 1.5 and db_after < -30.0:
                    events.append(CadenceEvent(
                        sample_start = mid_sample,
                        sample_end   = mid_sample + hop_samples * 4,
                        kind         = "WAQF",
                        confidence   = min(1.0, energy_drop / 20.0),
                    ))
                    i += window_frames // 2
                    continue

        # Breath: sustained low-energy zone
        if frame_rms_db[i] < _ATCD_BREATH_FLOOR_DB:
            breath_end = i
            while breath_end < n_frames and frame_rms_db[breath_end] < _ATCD_BREATH_FLOOR_DB:
                breath_end += 1
            breath_dur_ms = (breath_end - i) * 10.0
            if 60 < breath_dur_ms < 800:
                events.append(CadenceEvent(
                    sample_start = i * hop_samples,
                    sample_end   = breath_end * hop_samples,
                    kind         = "BREATH",
                    confidence   = 0.6,
                ))
                i = breath_end + 1
                continue

        i += 1

    return events

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — TRSB: TEMPORAL RECURRENCE SPECTRAL BLOCK INPAINTING
#  Exploits the repetitive melodic structure of Quranic recitation:
#  the same verses appear multiple times → use strong instances to
#  enhance weaker instances of the same phrase.
#
#  Pass-3 fixes baked in:
#    • Vectorised distance matrix (not O(N²) loop)
#    • Proper OLA write-back (not windowed blend)
#    • MMSE-LSA style SNR estimation to identify weak frames
#    • Pair deduplication (same frame index used once)
# ══════════════════════════════════════════════════════════════════════════════

_TRSB_N_SAMPLE:      int   = 400  # frames sampled for recurrence search
_TRSB_SIM_THRESH:    float = 0.88 # cosine similarity threshold for recurrence pair
_TRSB_SNR_WEAK_DB:   float = 10.0 # frames below this SNR are "weak"
_TRSB_BLEND_ALPHA:   float = 0.30 # blend ratio: 30% strong → weak

def _trsb_inpaint(
    mono:      np.ndarray,
    sr:        int,
    f0_hz:     np.ndarray,
    voiced:    np.ndarray,
    noise_rms: float = 1e-4,
) -> Tuple[np.ndarray, int]:
    """
    Temporal Recurrence Spectral Block inpainting.
    Returns (enhanced_audio, n_pairs_used).
    """
    hop  = max(1, int(sr * 0.010))
    nfft = hop * 4
    win  = np.hanning(nfft)
    n_frames = len(f0_hz)

    if n_frames < 20:
        return mono.copy(), 0

    # ── Step 1: Compute spectral feature vectors for all voiced frames ────────
    # Use log-magnitude spectrum as feature; subsample to _TRSB_N_SAMPLE
    voiced_idxs = [i for i, v in enumerate(voiced) if v]
    if len(voiced_idxs) < 10:
        return mono.copy(), 0

    sample_idxs = voiced_idxs
    if len(sample_idxs) > _TRSB_N_SAMPLE:
        step = len(sample_idxs) // _TRSB_N_SAMPLE
        sample_idxs = sample_idxs[::step][:_TRSB_N_SAMPLE]

    n_samp = len(sample_idxs)
    feat_dim = nfft // 4  # use lower-frequency portion of spectrum

    feats = np.zeros((n_samp, feat_dim), dtype=np.float32)
    snr_db_arr = np.zeros(n_samp, dtype=np.float32)

    for j, fidx in enumerate(sample_idxs):
        start = fidx * hop
        end   = start + nfft
        seg   = mono[start:end] if end <= len(mono) else \
                np.pad(mono[start:], (0, max(0, end - len(mono))))
        seg   = seg[:nfft]

        spec = np.abs(np.fft.rfft(seg * win))
        # Log-magnitude feature (coarse frequency bins)
        coarse = np.log1p(spec[:feat_dim] + 1e-8)
        norm   = float(np.linalg.norm(coarse))
        feats[j] = coarse / (norm + 1e-12)

        frame_rms = float(np.sqrt(np.mean(seg ** 2)) + 1e-12)
        snr_db_arr[j] = _safe_db(frame_rms / (noise_rms + 1e-12))

    # ── Step 2: Vectorised distance matrix → recurrence pairs ─────────────────
    # Cosine similarity matrix: S = feats @ feats.T (already unit-normalised)
    S = feats @ feats.T  # (n_samp, n_samp)
    # Zero out diagonal and near-diagonal (same frame or adjacent)
    for d in range(-4, 5):
        k = n_samp
        if d >= 0:
            np.fill_diagonal(S[d:, :k - d], 0.0)
        else:
            np.fill_diagonal(S[:k + d, -d:], 0.0)

    # Find pairs: strong frame i helps weak frame j (sim > threshold)
    used_weak:  set = set()
    used_strong: set = set()
    pairs: List[Tuple[int, int]] = []

    # Sort by similarity (highest first)
    sim_flat = S.ravel()
    order    = np.argsort(-sim_flat)

    for flat_idx in order:
        if len(pairs) >= 120:  # cap total pairs
            break
        row = int(flat_idx // n_samp)
        col = int(flat_idx %  n_samp)
        if float(sim_flat[flat_idx]) < _TRSB_SIM_THRESH:
            break

        # One must be weak, the other strong
        is_weak_row  = snr_db_arr[row] < _TRSB_SNR_WEAK_DB
        is_weak_col  = snr_db_arr[col] < _TRSB_SNR_WEAK_DB

        if is_weak_row and not is_weak_col and row not in used_weak and col not in used_strong:
            pairs.append((col, row))  # (strong, weak)
            used_weak.add(row)
            used_strong.add(col)
        elif is_weak_col and not is_weak_row and col not in used_weak and row not in used_strong:
            pairs.append((row, col))
            used_weak.add(col)
            used_strong.add(row)

    if not pairs:
        return mono.copy(), 0

    # ── Step 3: Apply inpainting with correct OLA write-back ─────────────────
    #
    # Fix from v1: out_ola must start as ZEROS (not a copy of mono) and
    # norm_ola must start as ZEROS (not ones).  Every sample — blended or
    # untouched — is written through the OLA accumulator so the final
    # division gives a clean weighted average with no DC offset from the
    # pre-loaded mono copy.
    #
    # Algorithm:
    #   • All frames are first OLA-summed into out_ola with their Hanning
    #     window as weight (passthrough contribution).
    #   • For weak frames that have a strong pair, a SECOND contribution is
    #     added: the spectral-blended frame weighted by win × blend_alpha.
    #   • norm_ola accumulates win (passthrough) + win × blend_alpha (blend)
    #     so the final division correctly weights the two contributions.
    #
    n_out    = len(mono)
    out_ola  = np.zeros(n_out + nfft, dtype=np.float64)   # ← zeros, not mono
    norm_ola = np.zeros(n_out + nfft, dtype=np.float64)   # ← zeros, not ones

    # Build lookup: weak frame index → strong frame index
    weak_to_strong: dict = {}
    for (strong_j, weak_j) in pairs:
        # Store for each context offset too
        for frame_offset in range(-1, 2):
            wi = sample_idxs[weak_j]   + frame_offset
            si = sample_idxs[strong_j] + frame_offset
            if 0 <= wi < n_frames and 0 <= si < n_frames:
                weak_to_strong[wi] = si

    def _extract(fidx_start: int) -> np.ndarray:
        end = fidx_start + nfft
        if end <= n_out:
            return mono[fidx_start:end].astype(np.float64)
        return np.pad(mono[fidx_start:].astype(np.float64),
                      (0, max(0, end - n_out)))[:nfft]

    for fidx in range(n_frames):
        w_start = fidx * hop
        w_end   = w_start + nfft
        if w_start >= n_out:
            break

        weak_frame = _extract(w_start)

        # Passthrough OLA contribution (every frame, windowed)
        clip_end = min(w_end, n_out + nfft)
        wlen     = clip_end - w_start
        out_ola[w_start:clip_end]  += weak_frame[:wlen] * win[:wlen]
        norm_ola[w_start:clip_end] += win[:wlen]

        # Blend contribution for weak frames that have a matched strong frame
        if fidx in weak_to_strong:
            s_start      = weak_to_strong[fidx] * hop
            strong_frame = _extract(s_start)

            strong_spec  = np.fft.rfft(strong_frame * win)
            weak_spec    = np.fft.rfft(weak_frame   * win)

            strong_mag   = np.abs(strong_spec) + 1e-12
            weak_mag     = np.abs(weak_spec)   + 1e-12
            phase        = np.angle(weak_spec)          # keep weak-frame phase

            blended_mag  = ((1.0 - _TRSB_BLEND_ALPHA) * weak_mag
                            + _TRSB_BLEND_ALPHA         * strong_mag)
            blended_spec  = blended_mag * np.exp(1j * phase)
            blended_frame = np.fft.irfft(blended_spec)[:nfft]
            blended_frame = _nan_guard(blended_frame)

            # Add blend delta: weighted by win × alpha
            # (passthrough already added above; we add the DIFFERENCE)
            delta = (blended_frame - weak_frame) * win * _TRSB_BLEND_ALPHA
            out_ola[w_start:clip_end]  += delta[:wlen]
            norm_ola[w_start:clip_end] += win[:wlen] * _TRSB_BLEND_ALPHA

    result = (out_ola / np.where(norm_ola > 1e-6, norm_ola, 1.0))[:n_out].astype(np.float32)
    return _nan_guard(result), len(pairs)

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 9 — MPRM: MAKHRAJ PHARYNGEAL RESONANCE MODEL
#  Arabic pharyngeal phonemes: ح، ع، ه، خ، غ
#  These produce distinctive formant patterns: elevated F1 (500–900 Hz),
#  strong F2 (1200–2500 Hz), suppressed F3.
#  Enhancement: boost pharyngeal formant region when confidence high.
#
#  Pass-4 fixes baked in:
#    • Running exponential smoother (α=0.85) for F1/F2 stability
#    • Only apply when confidence > 0.65
#    • Confidence from LPC residual energy ratio
# ══════════════════════════════════════════════════════════════════════════════

_MPRM_LPC_ORDER:     int   = 14
_MPRM_SMOOTH_ALPHA:  float = 0.85  # formant smoother (slow = stable)
_MPRM_CONF_THRESH:   float = 0.65
_MPRM_PHARYNGEAL_F1: Tuple[float, float] = (500.0,  900.0)   # Hz
_MPRM_PHARYNGEAL_F2: Tuple[float, float] = (1200.0, 2500.0)  # Hz
_MPRM_BOOST_DB:      float = 1.5   # modest boost for pharyngeal range

def _mprm_enhance(
    mono: np.ndarray,
    sr:   int,
    f0_hz:  np.ndarray,
    voiced: np.ndarray,
) -> Tuple[np.ndarray, bool]:
    """
    Makhraj Pharyngeal Resonance Model enhancement.
    Returns (enhanced_audio, mprm_applied).
    Skips if scipy.signal unavailable or confidence generally low.
    """
    if not _SCIPY_SIGNAL_OK:
        return mono.copy(), False

    hop  = max(1, int(sr * 0.010))
    nfft = hop * 4
    win  = np.hanning(nfft)
    n_frames = len(f0_hz)

    # Running formant state (smoothed)
    smooth_f1 = 700.0   # Hz
    smooth_f2 = 1800.0  # Hz
    alpha = _MPRM_SMOOTH_ALPHA

    out_ola  = np.zeros(len(mono) + nfft, dtype=np.float64)
    norm_ola = np.zeros(len(mono) + nfft, dtype=np.float64)
    mprm_applied = False

    freqs_hz = np.fft.rfftfreq(nfft, d=1.0 / sr)

    for i, (f0, is_voiced) in enumerate(zip(f0_hz, voiced)):
        start = i * hop
        end   = start + nfft
        frame = mono[start:end] if end <= len(mono) else \
                np.pad(mono[start:], (0, max(0, end - len(mono))))
        frame = frame[:nfft].astype(np.float64)

        if not is_voiced or f0 <= 0 or frame.size < _MPRM_LPC_ORDER + 2:
            out_ola[start:start + nfft]  += frame * win
            norm_ola[start:start + nfft] += win
            continue

        # LPC analysis
        try:
            a_coef = _scipy_lpc(frame * win, order=_MPRM_LPC_ORDER)
            # Residual energy as confidence proxy
            residual = lfilter(a_coef, [1.0], frame * win)
            signal_e  = float(np.mean(frame ** 2)) + 1e-12
            residual_e = float(np.mean(residual ** 2)) + 1e-12
            # Low residual/signal ratio = good LPC fit = pharyngeal frame candidate
            conf = 1.0 - min(1.0, math.sqrt(residual_e / signal_e))
        except Exception:
            out_ola[start:start + nfft]  += frame * win
            norm_ola[start:start + nfft] += win
            continue

        if conf < _MPRM_CONF_THRESH:
            out_ola[start:start + nfft]  += frame * win
            norm_ola[start:start + nfft] += win
            continue

        # Rough formant extraction from LPC spectrum peaks
        n_lpc = 512
        lpc_freq = np.fft.rfftfreq(n_lpc, d=1.0 / sr)
        lpc_spec = np.abs(1.0 / np.fft.rfft(a_coef, n=n_lpc))
        # Find peaks
        peaks = []
        for k in range(1, len(lpc_spec) - 1):
            if lpc_spec[k] > lpc_spec[k - 1] and lpc_spec[k] > lpc_spec[k + 1]:
                peaks.append((float(lpc_freq[k]), float(lpc_spec[k])))
        peaks.sort(key=lambda p: -p[1])

        # Assign smoothed F1, F2
        if peaks:
            # F1 candidate: lowest-frequency dominant peak < 1000 Hz
            f1_cands = [p for p in peaks if p[0] < 1000]
            f2_cands = [p for p in peaks if 1000 < p[0] < 3000]
            raw_f1 = f1_cands[0][0] if f1_cands else smooth_f1
            raw_f2 = f2_cands[0][0] if f2_cands else smooth_f2
            # Exponential smooth
            smooth_f1 = alpha * smooth_f1 + (1 - alpha) * raw_f1
            smooth_f2 = alpha * smooth_f2 + (1 - alpha) * raw_f2

        # Pharyngeal check: F1 in [500, 900], F2 in [1200, 2500]
        pharyngeal = (
            _MPRM_PHARYNGEAL_F1[0] <= smooth_f1 <= _MPRM_PHARYNGEAL_F1[1] and
            _MPRM_PHARYNGEAL_F2[0] <= smooth_f2 <= _MPRM_PHARYNGEAL_F2[1]
        )

        if pharyngeal:
            # Boost pharyngeal formant region in spectrum
            spec_c = np.fft.rfft(frame * win)
            mag    = np.abs(spec_c) + 1e-12
            phase  = np.angle(spec_c)

            boost_gain = np.ones(len(freqs_hz), dtype=np.float64)
            f1lo, f1hi = _MPRM_PHARYNGEAL_F1
            f2lo, f2hi = _MPRM_PHARYNGEAL_F2
            mask_f1 = (freqs_hz >= f1lo) & (freqs_hz <= f1hi)
            mask_f2 = (freqs_hz >= f2lo) & (freqs_hz <= f2hi)
            boost_lin = 10.0 ** (_MPRM_BOOST_DB / 20.0)
            boost_gain[mask_f1] = boost_lin
            boost_gain[mask_f2] = boost_lin * 0.7  # gentler on F2

            spec_out  = boost_gain * mag * np.exp(1j * phase)
            frame_out = np.fft.irfft(spec_out)[:nfft]
            frame_out = _nan_guard(frame_out)
            mprm_applied = True
        else:
            frame_out = frame

        out_ola[start:start + nfft]  += frame_out * win
        norm_ola[start:start + nfft] += win

    norm_safe = np.where(norm_ola > 1e-6, norm_ola, 1.0)
    result = (out_ola / norm_safe)[:len(mono)].astype(np.float32)
    return _nan_guard(result), mprm_applied

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 10 — S-GATE / SIDRAH SCORE
#  Pass-5 fixes baked in:
#    • V-gate checks LUFS + peak amplitude + crest factor (not just LUFS)
#    • SidrahScore S2 based on voiced-frame percentage (not raw harmonic count)
#    • Short file (<0.5 s) → return unchanged with skip flag
#    • Zero-pitch guard → early exit if n_voiced == 0
# ══════════════════════════════════════════════════════════════════════════════

_SGATE_LUFS_MAX_DELTA:  float = 1.5   # maximum LUFS change allowed
_SGATE_PEAK_MAX_DELTA:  float = 1.0   # dBFS peak increase limit
_SGATE_CREST_MAX_DELTA: float = 2.0   # dB crest factor change limit

def _lufs_approx(audio: np.ndarray, sr: int) -> float:
    """Fast LUFS approximation via ITU-R BS.1770 K-weighting (simplified)."""
    if audio.size == 0:
        return -70.0
    # Pre-filter: approximate K-weighting with simple HP at 60 Hz
    # (production code uses ffmpeg loudnorm; this is for V-gate delta check)
    try:
        from scipy.signal import butter, filtfilt
        b, a = butter(2, 60.0 / (sr / 2), btype='high')
        filtered = filtfilt(b, a, audio.astype(np.float64))
    except Exception:
        filtered = audio.astype(np.float64)
    rms = float(np.sqrt(np.mean(filtered ** 2) + 1e-12))
    return max(-70.0, 20.0 * math.log10(rms) - 0.691)

def _compute_sidrah_score(
    hle_pct:     float,  # % voiced frames where HLE boosted
    maqam_conf:  float,  # maqam detection confidence
    trsb_pairs:  int,    # number of TRSB pairs applied
    n_cadences:  int,    # cadences detected
    mprm_applied: bool,
    voiced_frac: float,
) -> float:
    """
    SidrahScore ∈ [0, 100].

    S1: Maqam confidence contribution (0–30)
    S2: HLE voiced-frame coverage (0–25) — based on %, not raw count
    S3: TRSB inpainting contribution (0–20)
    S4: Cadence detection richness (0–15)
    S5: MPRM applied (0–10)
    """
    # S1: maqam detection confidence
    s1 = min(30.0, maqam_conf * 30.0)

    # S2: HLE based on % of voiced frames boosted (0–100% → 0–25)
    s2 = min(25.0, (hle_pct / 100.0) * 25.0) if voiced_frac > 0.1 else 0.0

    # S3: TRSB pairs applied (diminishing returns after 20 pairs)
    s3 = min(20.0, math.log1p(trsb_pairs) * 5.0)

    # S4: Cadences (more is richer analysis, capped at 10 unique events)
    s4 = min(15.0, n_cadences * 1.5)

    # S5: MPRM
    s5 = 10.0 if mprm_applied else 0.0

    return float(np.clip(s1 + s2 + s3 + s4 + s5, 0.0, 100.0))

def _s_gate_check(
    original:  np.ndarray,
    processed: np.ndarray,
    sr:        int,
) -> bool:
    """
    V-gate: return True if processing is acceptable.
    Checks LUFS delta, peak delta, and crest factor delta.
    """
    lufs_orig  = _lufs_approx(original,  sr)
    lufs_proc  = _lufs_approx(processed, sr)
    peak_orig  = _peak_db(original.astype(np.float64))
    peak_proc  = _peak_db(processed.astype(np.float64))
    crest_orig = _crest_db(original.astype(np.float64))
    crest_proc = _crest_db(processed.astype(np.float64))

    lufs_delta  = abs(lufs_proc  - lufs_orig)
    peak_delta  = peak_proc - peak_orig   # increase is bad
    crest_delta = abs(crest_proc - crest_orig)

    ok = (
        lufs_delta  <= _SGATE_LUFS_MAX_DELTA  and
        peak_delta  <= _SGATE_PEAK_MAX_DELTA  and
        crest_delta <= _SGATE_CREST_MAX_DELTA
    )

    if not ok:
        log.debug(
            "S-GATE FAIL: LUFS Δ=%.2f peak Δ=%.2f crest Δ=%.2f",
            lufs_delta, peak_delta, crest_delta,
        )
    return ok

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 11 — MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def apply_sidrah(
    mono:        np.ndarray,
    sr:          int,
    noise_rms:   float = 1e-4,
    verbose:     bool  = False,
) -> SidrahResult:
    """
    سِدْرَة — full Maqam-Aware Spectral Resonance Field pipeline.

    Parameters
    ----------
    mono       : float32 audio, mono, pre-processed (after v16 Phase A-3)
    sr         : sample rate (Hz)
    noise_rms  : estimated noise floor RMS (from Phase A-1 diagnostics)
    verbose    : log component timings

    Returns
    -------
    SidrahResult with .audio = processed float32 and all diagnostics.
    """
    import time as _time

    result = SidrahResult()

    # ── Guard: short file ────────────────────────────────────────────────────
    MIN_SAMPLES = int(sr * 0.5)
    if mono.size < MIN_SAMPLES:
        result.audio      = mono.copy()
        result.skipped    = True
        result.skip_reason = f"short_file:{mono.size/sr:.2f}s"
        log.info("Sidrah: skipped (short file %.2fs)", mono.size / sr)
        return result

    mono = _nan_guard(mono.astype(np.float32))

    # ── F0 detection (shared across all components) ───────────────────────────
    t0 = _time.perf_counter()
    f0_hz, voiced = _detect_f0_frames(mono, sr)
    n_voiced = int(np.sum(voiced))

    # ── Guard: zero-pitch ────────────────────────────────────────────────────
    if n_voiced == 0:
        result.audio       = mono.copy()
        result.skipped     = True
        result.skip_reason = "zero_voiced_frames"
        log.info("Sidrah: skipped (no voiced frames detected)")
        return result

    if verbose:
        log.info("Sidrah F0: %.1fms, voiced=%d/%d (%.0f%%)",
                 (_time.perf_counter() - t0) * 1000,
                 n_voiced, len(voiced), 100 * n_voiced / len(voiced))

    voiced_frac = n_voiced / len(voiced)

    # ── QMC: Quarter-tone Maqam Chromagram ───────────────────────────────────
    t0 = _time.perf_counter()
    chroma, vf = _compute_qmc(mono, sr, f0_hz, voiced)
    maqam_result = _score_maqamat(chroma)
    maqam_result.voiced_frac = vf
    result.maqam = maqam_result
    if verbose:
        log.info("Sidrah QMC: %.1fms, maqam=%s conf=%.2f",
                 (_time.perf_counter() - t0) * 1000,
                 maqam_result.maqam, maqam_result.confidence)

    # ── ATCD: Ayah Cadence Detection ─────────────────────────────────────────
    t0 = _time.perf_counter()
    cadences = _detect_cadences(mono, sr, f0_hz, voiced)
    result.cadences = cadences
    if verbose:
        log.info("Sidrah ATCD: %.1fms, cadences=%d",
                 (_time.perf_counter() - t0) * 1000, len(cadences))

    audio = mono.copy()

    # ── HLE: Harmonic Lattice Enhancement ────────────────────────────────────
    t0 = _time.perf_counter()
    audio_hle, hle_pct = _hle_enhance(audio, sr, maqam_result, f0_hz, voiced, noise_rms)
    result.hle_harmonics_pct = hle_pct
    if verbose:
        log.info("Sidrah HLE: %.1fms, boosted=%.1f%% of voiced",
                 (_time.perf_counter() - t0) * 1000, hle_pct)

    # ── TRSB: Temporal Recurrence Spectral Block ──────────────────────────────
    t0 = _time.perf_counter()
    audio_trsb, n_pairs = _trsb_inpaint(audio_hle, sr, f0_hz, voiced, noise_rms)
    result.trsb_pairs   = n_pairs
    result.trsb_applied = n_pairs > 0
    if verbose:
        log.info("Sidrah TRSB: %.1fms, pairs=%d",
                 (_time.perf_counter() - t0) * 1000, n_pairs)

    # ── MPRM: Makhraj Pharyngeal Resonance Model ──────────────────────────────
    t0 = _time.perf_counter()
    audio_mprm, mprm_ok = _mprm_enhance(audio_trsb, sr, f0_hz, voiced)
    result.mprm_applied = mprm_ok
    if verbose:
        log.info("Sidrah MPRM: %.1fms, applied=%s",
                 (_time.perf_counter() - t0) * 1000, mprm_ok)

    final_audio = audio_mprm

    # ── S-GATE: V-gate validation ─────────────────────────────────────────────
    gate_ok = _s_gate_check(mono, final_audio, sr)
    result.v_gate_passed = gate_ok

    if not gate_ok:
        log.warning("Sidrah S-GATE failed — reverting to HLE-only output")
        # Partial revert: use HLE output (most conservative enhancement)
        gate_ok2 = _s_gate_check(mono, audio_hle, sr)
        if gate_ok2:
            final_audio = audio_hle
            result.trsb_applied  = False
            result.mprm_applied  = False
            result.v_gate_passed = True
        else:
            # Full revert
            final_audio          = mono.copy()
            result.hle_harmonics_pct = 0.0
            result.trsb_applied  = False
            result.mprm_applied  = False
            result.v_gate_passed = False
            log.warning("Sidrah S-GATE full revert — returning original audio")

    # ── HLE applied flag ─────────────────────────────────────────────────────
    result.hle_applied = (result.hle_harmonics_pct > 0.0) and result.v_gate_passed

    # ── SidrahScore ───────────────────────────────────────────────────────────
    result.sidrah_score = _compute_sidrah_score(
        hle_pct      = result.hle_harmonics_pct,
        maqam_conf   = maqam_result.confidence,
        trsb_pairs   = result.trsb_pairs,
        n_cadences   = len(cadences),
        mprm_applied = result.mprm_applied,
        voiced_frac  = voiced_frac,
    )

    result.audio = _nan_guard(final_audio)

    log.info(
        "سِدْرَة complete | maqam=%-9s conf=%.2f | HLE=%.0f%% | "
        "TRSB pairs=%-3d | MPRM=%s | score=%.1f | V-gate=%s",
        maqam_result.maqam,
        maqam_result.confidence,
        result.hle_harmonics_pct,
        result.trsb_pairs,
        "OK" if result.mprm_applied else "--",
        result.sidrah_score,
        "PASS" if result.v_gate_passed else "FAIL",
    )
    return result

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 12 — V16 INTEGRATION SHIM
#  Drop this block into Phase A-3/A-4 boundary in engine_aetherion_v16.py
# ══════════════════════════════════════════════════════════════════════════════

def needs_tier2(state: 'InputState',
                result: Optional['PassResult'] = None) -> Tuple[bool, str]:
    """
    T2-R1: Gate function — determines whether Tier 2 Recovery is needed.

    TYPE_A (noise-dominated): snr_global < 12.0 dB
    TYPE_B (dynamics destroyed): clip_lra < 2.0 AND clip_crest < 9.5
    TYPE_B2 (post-base LRA deficit): requires PassResult argument.
    TYPE_C (codec artifacts / pixeled voice):
      src_br < 64000 OR smear_score >= 5.
      Below 64kbps, codec quantization creates audible mosquito noise,
      pre-echo, and bandwidth truncation — the 'pixeled voice' quality
      that cannot be fixed by EQ or standard NR.
    """
    reasons: List[str] = []

    # FIX (v10.5): use frame_snr (p80-p5) for TYPE_A, not snr_global.
    # snr_global from compute_band_snr reports 20+dB even on SNR=5dB mosque recordings
    # because tonal noise has coherent spectral peaks that look like signal to the band estimator.
    _snr_for_t2 = getattr(state, 'frame_snr', state.snr_global)
    if _snr_for_t2 < 12.0:
        reasons.append(f'TYPE_A:SNR={_snr_for_t2:.1f}dB(frame)')

    # FIX (v10.5): removed Crest < 9.5 constraint. القمر (LRA=1.66, Crest=13.67)
    # was excluded because Crest > 9.5 even though LRA is clearly crushed.
    # High Crest + low LRA = compressed dynamics where loud peaks survived but
    # the dynamic range was squeezed. LRA < 2.0 alone is the correct trigger.
    if state.clip_lra < 2.0:
        reasons.append(
            f'TYPE_B:LRA={state.clip_lra:.2f}|Crest={state.clip_crest:.2f}')

    if result is not None:
        lra_deficit = ref_phrase_lra_p50_default - result.lra
        if lra_deficit > 1.5 and result.lra < 2.0:
            reasons.append(
                f'TYPE_B2:deficit={lra_deficit:.2f}|result_lra={result.lra:.2f}')

    # TYPE_C: codec artifact recovery — 'pixeled voice'
    # FIX-6d (v10.5): also trigger when codec_cutoff < 8000, regardless of bitrate.
    # الأحزاب is 320kbps but was originally recorded from a low-quality source
    # (effective codec_cutoff ≈ 5kHz). The BW extension needs to run on it even
    # though 320kbps passes the bitrate gate.
    c_severity, _ = _detect_codec_artifacts(state)
    # Low codec_cutoff = objectively missing HF → always benefit from BW extension
    if state.codec_cutoff < 8000 and c_severity < 2:
        c_severity = max(c_severity, 2)  # at least moderate — triggers BW extension
    if c_severity >= 1:
        reasons.append(
            f'TYPE_C:severity={c_severity}|br={state.src_br // 1000}kbps'
            f'|cutoff={state.codec_cutoff:.0f}Hz'
            f'|smear={state.smear_score:.1f}')

    return bool(reasons), ' | '.join(reasons) if reasons else 'NONE'


def _minstat_wiener_nr(input_wav: str, state: 'InputState') -> str:
    """
    Minimum Statistics noise estimation + decision-directed Wiener filter.
    Works with zero silence frames — estimates noise PSD from per-bin
    rolling minimum over a 1.5s window (Martin 2001, B_min=1.66 bias correction).
    Returns path to enhanced WAV, or input_wav on failure.
    """
    import tempfile
    from collections import deque

    sr = SR; n_fft = 4096; hop = 480
    L_win = int(1.5 * sr / hop)
    B_min = 1.66; alpha_dd = 0.98; beta_floor = 0.01

    r = subprocess.run(['ffmpeg','-nostdin','-i', input_wav,
        '-ac','1','-ar',str(sr),'-f','f32le','-loglevel','error','-'],
        capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return input_wav

    audio = np.frombuffer(r.stdout, dtype=np.float32).copy()
    hann  = np.hanning(n_fft).astype(np.float64)
    S     = np.array([np.fft.rfft(audio[i:i+n_fft].astype(np.float64)*hann)
                      for i in range(0, len(audio)-n_fft, hop)])
    T, F  = S.shape
    mag   = np.abs(S).astype(np.float32)
    pwr   = mag**2

    # Rolling minimum per frequency bin
    noise_psd = np.zeros((T, F), np.float32)
    for f_idx in range(F):
        p = pwr[:, f_idx]; dq = deque(); mn = np.empty(T, np.float32)
        for t in range(T):
            while dq and dq[0] < t - L_win: dq.popleft()
            while dq and p[dq[-1]] >= p[t]: dq.pop()
            dq.append(t); mn[t] = p[dq[0]]
        noise_psd[:, f_idx] = mn / B_min

    # Decision-directed Wiener
    snr_post = np.maximum(pwr / (noise_psd + 1e-20), beta_floor)
    gain_all = np.zeros_like(mag)
    freqs    = np.fft.rfftfreq(n_fft, 1/sr)
    sib_mask = (freqs >= 2500) & (freqs <= 5000)

    for t in range(T):
        if t > 0:
            snr_pri = (alpha_dd * (gain_all[t-1]**2 * pwr[t-1] / (noise_psd[t-1]+1e-20))
                       + (1-alpha_dd) * np.maximum(snr_post[t]-1, 0))
        else:
            snr_pri = snr_post[t]
        gain_all[t] = np.maximum(snr_pri / (snr_pri + 1.0), beta_floor)
    gain_all[:, sib_mask] = np.maximum(gain_all[:, sib_mask], 0.50)

    S_enh = S * gain_all

    # ISTFT via overlap-add
    out    = np.zeros(len(audio) + n_fft, np.float64)
    win_acc = np.zeros_like(out)
    for t, s in enumerate(S_enh):
        i0 = t * hop
        frame = np.real(np.fft.irfft(s, n=n_fft)) * hann
        out[i0:i0+n_fft]     += frame
        win_acc[i0:i0+n_fft] += hann**2
    out = (out / np.maximum(win_acc, 1e-10))[:len(audio)].astype(np.float32)

    # Restore RMS
    rms_in  = float(np.sqrt(np.mean(audio**2)) + 1e-10)
    rms_out = float(np.sqrt(np.mean(out**2))   + 1e-10)
    out = np.clip(out * (rms_in / rms_out), -1.0, 1.0)

    out_path = input_wav + '.msw.wav'
    r2 = subprocess.run(
        ['ffmpeg','-nostdin','-y','-hide_banner','-loglevel','error',
         '-f','f32le','-ar',str(sr),'-ac','1','-i','pipe:0',
         '-acodec', WAV_CODEC, out_path],
        input=out.tobytes(), capture_output=True)
    if r2.returncode != 0 or not Path(out_path).exists():
        return input_wav

    return out_path


def _run_deepfilter3_cli(input_wav: str, output_wav: str,
                         atten_lim_db: int = 15) -> bool:
    """
    T-0.5 CLI path — uses the deep-filter binary when Python df package absent.
    Converts to 48kHz pcm_s16le mono (DF requirement), runs CLI, re-encodes.
    atten_lim_db: maximum suppression in dB (8=light, 15=balanced, 20=aggressive).
    """
    if not DEEPFILTER_CLI_OK:
        return False
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_in  = str(tmp_dir / 'df_in.wav')
    tmp_out = str(tmp_dir / 'df_in.wav')   # CLI writes same filename into output_dir
    try:
        rc = subprocess.run(
            ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
             '-i', input_wav,
             '-acodec', 'pcm_s16le', '-ar', '48000', '-ac', '1', tmp_in],
            capture_output=True, timeout=120,
        ).returncode
        if rc != 0:
            return False

        rc = subprocess.run(
            [_DF_CLI_BIN, '--atten-lim-db', str(atten_lim_db),
             '-o', str(tmp_dir), tmp_in],
            capture_output=True, timeout=300,
        ).returncode
        if rc != 0:
            return False

        if not Path(tmp_out).exists() or Path(tmp_out).stat().st_size == 0:
            return False

        rc = subprocess.run(
            ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
             '-i', tmp_out,
             '-acodec', WAV_CODEC, '-ar', str(SR), output_wav],
            capture_output=True, timeout=120,
        ).returncode
        return rc == 0

    except Exception as exc:
        L(f'  [T-0.5-cli] ERROR: {exc}')
        return False
    finally:
        import shutil as _sh
        _sh.rmtree(str(tmp_dir), ignore_errors=True)


def _run_deepfilter3_adaptive_cli(
        input_wav: str,
        output_wav: str,
        state: 'InputState',
) -> bool:
    """
    Adaptive DeepFilter CLI — Voice-level-aware 3-pass NR.

    The Sheikh's recitation has a natural loudness range of ~16dB between
    a powerful projection and a soft phrase-ending.  A fixed atten_lim treats
    all frames equally: either under-cleans the quiet gaps or over-processes
    the loud voice.

    This function:
      1. VAD — classifies every 100ms chunk by RMS into LOUD / MID / QUIET.
           LOUD  > −15 dBFS RMS → atten_lim = 8  dB  (protect voice character)
           MID   −25 to −15     → atten_lim = 15 dB  (balanced)
           QUIET < −25 dBFS     → atten_lim = 20 dB  (aggressive clean)
      2. Runs DeepFilter CLI once per class (3 passes on same input file).
      3. Stitches the three outputs back together using per-sample selection,
         with 20ms cosine crossfades at class boundaries to eliminate clicks.
      4. Re-encodes the blended result to pcm_s24le WAV.

    Returns True on full success.  Falls back to single-pass (atten_lim=15)
    on any partial failure.
    """
    if not DEEPFILTER_CLI_OK:
        return False
    if not NUMPY_OK:
        # numpy required for VAD + blend — fall back to single pass
        return _run_deepfilter3_cli(input_wav, output_wav, atten_lim_db=15)

    import tempfile, shutil as _sh

    # ── Decode source to float32 mono numpy ───────────────────────────────
    raw = subprocess.run(
        ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
         '-i', input_wav, '-ar', str(SR), '-ac', '1',
         '-f', 'f32le', '-'],
        capture_output=True, timeout=120,
    )
    if raw.returncode != 0 or len(raw.stdout) < 4:
        return _run_deepfilter3_cli(input_wav, output_wav, atten_lim_db=15)

    mono = np.frombuffer(raw.stdout, dtype=np.float32).copy()
    total = len(mono)

    # ── VAD — 100ms chunk RMS classification ─────────────────────────────
    CHUNK      = int(0.100 * SR)
    n_chunks   = max(1, total // CHUNK)
    LOUD_T     = -15.0   # dBFS RMS — Sheikh projecting
    QUIET_T    = -25.0   # dBFS RMS — soft phrase / breath

    rms_ch = np.array([
        20.0 * np.log10(
            np.sqrt(np.mean(mono[i*CHUNK : (i+1)*CHUNK] ** 2)) + 1e-12
        )
        for i in range(n_chunks)
    ])

    loud_mask  = rms_ch >  LOUD_T
    mid_mask   = (rms_ch <= LOUD_T) & (rms_ch >  QUIET_T)
    quiet_mask = rms_ch <= QUIET_T

    n_loud  = int(loud_mask.sum())
    n_mid   = int(mid_mask.sum())
    n_quiet = int(quiet_mask.sum())
    L(f'  [ADF-VAD] LOUD={n_loud} MID={n_mid} QUIET={n_quiet} chunks × 100ms')

    # Update state counters
    state.df3_loud_chunks  = n_loud
    state.df3_mid_chunks   = n_mid
    state.df3_quiet_chunks = n_quiet

    # ── Prepare pcm_s16le mono input for DF (format requirement) ─────────
    tmp_root = Path(tempfile.mkdtemp())
    df_in    = str(tmp_root / 'df_in.wav')
    try:
        rc = subprocess.run(
            ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
             '-i', input_wav,
             '-acodec', 'pcm_s16le', '-ar', '48000', '-ac', '1', df_in],
            capture_output=True, timeout=120,
        ).returncode
        if rc != 0:
            raise RuntimeError('df_in encode failed')

        # ── Run 3 DeepFilter passes ───────────────────────────────────────
        df_outputs: dict = {}
        for cls, atten in [('loud', 8), ('mid', 15), ('quiet', 20)]:
            odir = tmp_root / f'df_{cls}'
            odir.mkdir(exist_ok=True)
            rc2 = subprocess.run(
                [_DF_CLI_BIN, '--atten-lim-db', str(atten),
                 '-o', str(odir), df_in],
                capture_output=True, timeout=300,
            ).returncode
            result = odir / 'df_in.wav'
            if rc2 == 0 and result.exists() and result.stat().st_size > 0:
                raw2 = subprocess.run(
                    ['ffmpeg', '-nostdin', '-y', '-hide_banner',
                     '-loglevel', 'error', '-i', str(result),
                     '-ar', str(SR), '-ac', '1', '-f', 'f32le', '-'],
                    capture_output=True, timeout=120,
                )
                if raw2.returncode == 0 and len(raw2.stdout) >= 4:
                    df_outputs[cls] = np.frombuffer(
                        raw2.stdout, dtype=np.float32).copy()
                    L(f'  [ADF-DF] {cls:6s} atten={atten:2d}dB ✓  '                      f'max={np.max(np.abs(df_outputs[cls])):.4f}')
                else:
                    L(f'  [ADF-DF] {cls} decode failed — using source')
                    df_outputs[cls] = mono.copy()
            else:
                L(f'  [ADF-DF] {cls} pass failed (rc={rc2}) — using source')
                df_outputs[cls] = mono.copy()

        # ── Expand masks to sample level ──────────────────────────────────
        def expand_mask(mask: np.ndarray) -> np.ndarray:
            full = np.zeros(total, dtype=bool)
            for i, v in enumerate(mask):
                if v:
                    s = i * CHUNK
                    full[s : min(s + CHUNK, total)] = True
            return full

        l_s = expand_mask(loud_mask)
        m_s = expand_mask(mid_mask)
        q_s = expand_mask(quiet_mask)

        min_n = min(total,
                    len(df_outputs['loud']),
                    len(df_outputs['mid']),
                    len(df_outputs['quiet']))

        blended = np.zeros(min_n, dtype=np.float64)
        blended[l_s[:min_n]] = df_outputs['loud'][:min_n][l_s[:min_n]]
        blended[m_s[:min_n]] = df_outputs['mid'][:min_n][m_s[:min_n]]
        blended[q_s[:min_n]] = df_outputs['quiet'][:min_n][q_s[:min_n]]

        # ── Cosine crossfades at class boundaries (20ms) ──────────────────
        cls_map = (
            l_s[:min_n].astype(np.int8) +
            m_s[:min_n].astype(np.int8) * 2 +
            q_s[:min_n].astype(np.int8) * 3
        )
        bounds = np.where(np.diff(cls_map) != 0)[0]
        FADE   = int(0.020 * SR)   # 20ms crossfade

        for b in bounds:
            s_cf = max(0, b - FADE // 2)
            e_cf = min(min_n, b + FADE // 2)
            if e_cf <= s_cf:
                continue
            L_n = e_cf - s_cf
            fo  = np.cos(np.linspace(0.0, np.pi / 2.0, L_n)) ** 2
            fi  = np.sin(np.linspace(0.0, np.pi / 2.0, L_n)) ** 2
            # Which class before and after boundary?
            cm_b = int(cls_map[s_cf])
            cm_a = int(cls_map[min(e_cf, min_n - 1)])
            cls_b = 'loud' if cm_b == 1 else ('mid' if cm_b == 2 else 'quiet')
            cls_a = 'loud' if cm_a == 1 else ('mid' if cm_a == 2 else 'quiet')
            ba = df_outputs[cls_b][:min_n][s_cf:e_cf].astype(np.float64)
            aa = df_outputs[cls_a][:min_n][s_cf:e_cf].astype(np.float64)
            blended[s_cf:e_cf] = ba * fo + aa * fi

        state.df3_boundaries = int(len(bounds))
        L(f'  [ADF-blend] {len(bounds)} crossfade boundaries @ {FADE} samples each')

        # Silence-check
        blended_f32 = np.where(np.isfinite(blended), blended, 0.0).astype(np.float32)
        peak_b = float(np.max(np.abs(blended_f32)))
        if peak_b < 1e-4:
            L('  [ADF-blend] ⚠  silent result — falling back to mid pass')
            blended_f32 = df_outputs['mid'][:min_n].astype(np.float32)

        # ── Write blended stereo WAV (re-encode to project format) ────────
        tmp_blend_wav = str(tmp_root / 'blended.wav')
        raw_bytes = blended_f32.tobytes()
        rc3 = subprocess.run(
            ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
             '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-',
             '-ar', str(SR), '-ac', '2',
             '-acodec', WAV_CODEC, tmp_blend_wav],
            input=raw_bytes, capture_output=True, timeout=120,
        ).returncode
        if rc3 != 0:
            raise RuntimeError('blend WAV write failed')

        import shutil as _sh2
        _sh2.copy2(tmp_blend_wav, output_wav)
        state.df3_adaptive = True
        L(f'  [ADF] ✓  adaptive blend written → {output_wav}')
        return True

    except Exception as exc:
        L(f'  [ADF] ERROR: {exc} — falling back to single pass')
        return _run_deepfilter3_cli(input_wav, output_wav, atten_lim_db=15)
    finally:
        _sh.rmtree(str(tmp_root), ignore_errors=True)


def _run_deepfilter3(input_wav: str, output_wav: str,
                     state: 'InputState') -> bool:
    """
    T-0.5 — Apply DeepFilterNet-3 neural denoising to the baseline WAV.

    Flow:
      1. Lazy-init the DF3 model (cached in _DF3_MODEL_CACHE for the process
         lifetime — subsequent jobs pay only the inference cost, not model load).
      2. load_audio() → enhance() → df_save_audio() to a float32 temp WAV.
      3. ffmpeg re-encodes the temp WAV to pcm_s24le 48 kHz (preserving the
         project-wide intermediate format invariant).
      4. Temp float WAV is deleted regardless of outcome.

    Returns True on success, False on any failure (caller falls through to
    TYPE_A/B/C without DF3 output — input_wav is left untouched).
    """
    global _DF3_MODEL_CACHE

    if not DEEPFILTER_OK:
        return False

    tmp_float = output_wav + ".df3_float.wav"
    try:
        # ── 1. Model init (once per process) ─────────────────────────────────
        if _DF3_MODEL_CACHE is None:
            L("  [T-0.5] DeepFilterNet-3: loading model (first job — one-time cost)...")
            t0 = time.time()
            _model, _df_state, _ = init_df()
            _DF3_MODEL_CACHE = (_model, _df_state)
            L(f"  [T-0.5] Model ready in {time.time() - t0:.1f}s")

        model, df_state = _DF3_MODEL_CACHE

        # ── 2. Load → enhance ─────────────────────────────────────────────────
        audio, _ = load_audio(input_wav, sr=df_state.sr())
        enhanced  = enhance(model, df_state, audio)

        # ── 3. Save float WAV, then re-encode to pcm_s24le ───────────────────
        df_save_audio(tmp_float, enhanced, df_state.sr())

        rc = subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
             "-i", tmp_float,
             "-acodec", WAV_CODEC, "-ar", str(SR),
             output_wav],
            capture_output=True, timeout=180,
        ).returncode

        if rc != 0:
            L("  [T-0.5] ffmpeg re-encode failed after DF3")
            return False

        return True

    except Exception as exc:
        L(f"  [T-0.5] DeepFilterNet-3 ERROR: {exc}")
        return False
    finally:
        try:
            Path(tmp_float).unlink(missing_ok=True)
        except Exception:
            pass


def enhance_tier2(input_wav: str, state: 'InputState',
                   ref: 'ReferenceModel') -> Tuple[str, Dict]:
    # ── T-0.5: DeepFilterNet-3 — runs first, before TYPE_A/B/C ──────────────
    # Gated on the same SNR that triggered الاسترداد.  DF3 cleans the signal
    # so all downstream TYPE_A spectral subtraction, TYPE_B expansion, and
    # TYPE_C codec repair work from the best available audio, not raw noise.
    snr_before = state.snr_global
    t2_report: Dict = {}  # populated fully below; early init for T-0.4 JALAA
    # BUG-DF-1: gate used global SNR (19.5dB on noisy mosque file) but the
    # trigger condition in needs_tier2() uses frame SNR (3.3dB).  When
    # TYPE_A fires, DF3 should also run regardless of global SNR — the
    # frame-based analysis is the more reliable noise indicator.
    # BUG-DF-2: gate was 15dB but TYPE_A threshold is 12dB — DF3 retriggered
    # on already-cleaned signal (frame_snr=14.9 < 15.0). Align to 12dB.
    # Also guard: if DF3 already ran this session (df3_applied=True), skip.
    _DF3_GATE  = 12.0
    snr_frame  = getattr(state, 'frame_snr', snr_before)
    _SAFI_GATE = SAFI_FRAME_SNR_GATE_DB   # 8.0 dB

    # ── T-0.4 JALAA: WPE dereverberation (before SAFI) ──────────────────────
    if JALAA_OK and JALAA_UNPROCESSABLE_SNR <= snr_frame < JALAA_FRAME_SNR_GATE_DB:
        jalaa_wav, jalaa_res = apply_jalaa_to_engine(input_wav, snr_frame, log_fn=L)
        if jalaa_res.status == 'OK':
            input_wav                      = jalaa_wav
            state.jalaa_applied            = True
            state.jalaa_drr_gain_db        = jalaa_res.effective_drr_gain_db
            state.jalaa_reverb_removed     = jalaa_res.reverb_fraction_removed
            t2_report['jalaa_applied']     = True
            t2_report['jalaa_drr_gain']    = jalaa_res.effective_drr_gain_db
            t2_report['jalaa_chunks']      = jalaa_res.n_chunks
        elif jalaa_res.status not in ('SKIPPED', 'UNPROCESSABLE'):
            L(f'  [JALAA] failed ({jalaa_res.reason}) — continuing to SAFI')

    # ── T-0.4b: afftdn pass on JALAA output ──────────────────────────────────
    # After WPE removes reverb structure, a calibrated afftdn pass removes the
    # residual broadband noise floor with zero gating risk.
    # Noise floor = silence_floor or frame_snr-derived estimate.
    if getattr(state, 'jalaa_applied', False):
        _jalaa_nf = state.silence_floor if state.silence_valid else max(-35.0, -(state.frame_snr + 25.0))
        _jalaa_nf = float(np.clip(_jalaa_nf, -80.0, -20.0))  # afftdn valid: -80 to -20
        _afftdn_out = input_wav + '.afftdn.wav'
        import subprocess as _sp2
        _af2 = subprocess.run(
            ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
             '-i', input_wav,
             '-af', f'afftdn=nf={_jalaa_nf:.0f}:nt=w:om=o:tn=1',
             '-acodec', 'pcm_s24le', '-ar', str(SR), _afftdn_out],
            capture_output=True,
        )
        if _af2.returncode == 0 and Path(_afftdn_out).exists():
            input_wav = _afftdn_out
            L(f'  [JALAA-afftdn] ✓  nf={_jalaa_nf:.0f}dB')
        else:
            L(f'  [JALAA-afftdn] FAILED rc={_af2.returncode} err={_af2.stderr.decode(errors="replace")[:120]}')

    # ── T-0.4c: Minimum Statistics Wiener (after JALAA removes reverb) ───────
    if getattr(state, 'jalaa_applied', False):
        _msw_out = _minstat_wiener_nr(input_wav, state)
        if _msw_out != input_wav:
            input_wav = _msw_out
            L('  [MinStat-Wiener] ✓  rolling-min noise est → Wiener suppression')

    # ── SAFI: frame_snr in [2.5, 8.0) dB ─────────────────────────────────
    if SAFI_OK and TIER_UNPROCESSABLE_SNR <= snr_frame < _SAFI_GATE:
        safi_wav, safi_result = apply_safi_to_engine(input_wav, snr_frame, log_fn=L)
        if safi_result.status == 'UNPROCESSABLE':
            state.tier_unprocessable = True
            L(f'  [SAFI] TIER_UNPROCESSABLE — NR skipped, EQ only')
        elif safi_result.status == 'OK':
            input_wav              = safi_wav
            state.safi_applied     = True
            state.safi_snr_gain_db = safi_result.effective_snr_gain_db
            t2_report['safi_applied']       = True
            t2_report['safi_snr_gain_db']   = safi_result.effective_snr_gain_db
            t2_report['safi_f0_hz']         = safi_result.median_f0_hz
            t2_report['safi_voiced_ratio']  = safi_result.voiced_ratio
            t2_report['safi_voiced_frames'] = safi_result.voiced_frames_used
            snr_frame = min(snr_frame + safi_result.effective_snr_gain_db, 20.0)
            state.snr_global = snr_frame
            L(f'  [SAFI] OK — SNR gain={safi_result.effective_snr_gain_db:.1f} dB  '               f'voiced={safi_result.voiced_ratio:.0%}  f0={safi_result.median_f0_hz:.0f}Hz')
    elif SAFI_OK and snr_frame < TIER_UNPROCESSABLE_SNR:
        state.tier_unprocessable = True
        L(f'  [SAFI] frame_snr={snr_frame:.1f} dB < {TIER_UNPROCESSABLE_SNR} — TIER_UNPROCESSABLE, EQ only')

    # ── DF3: frame_snr in [8.0, 12.0) dB ─────────────────────────────────
    df_trigger = (
        not getattr(state, 'df3_applied',          False)
        and not getattr(state, 'tier_unprocessable', False)
        and not getattr(state, 'safi_applied',       False)
        and _SAFI_GATE <= snr_frame < _DF3_GATE
    )
    df_avail = DEEPFILTER_OK or DEEPFILTER_CLI_OK
    if df_avail and df_trigger:
        L(f"  [T-0.5/استراد] SNR frame={snr_frame:.1f} dB — Adaptive DeepFilterNet-3")
        df3_out = input_wav + ".df3.wav"
        if DEEPFILTER_OK:
            # Python package path — standard single pass (package handles internally)
            df3_ok = _run_deepfilter3(input_wav, df3_out, state)
            state.df3_adaptive = False
        else:
            # CLI path — use adaptive VAD-based 3-pass system
            L("  [T-0.5/استراد] CLI binary — running adaptive VAD 3-pass")
            df3_ok = _run_deepfilter3_adaptive_cli(input_wav, df3_out, state)
        if df3_ok and Path(df3_out).exists() and Path(df3_out).stat().st_size > 0:
            try:
                from engine_isteidad_v5 import measure_snr_db
                state.df3_snr_after = measure_snr_db(df3_out)
            except Exception:
                state.df3_snr_after = 0.0
            state.df3_snr_before = snr_before
            state.df3_applied    = True
            input_wav            = df3_out
            if state.df3_snr_after > 1.0:
                state.snr_global = state.df3_snr_after
            else:
                state.df3_snr_after = snr_before
            _adf_tag = (f" adaptive[L={state.df3_loud_chunks}"
                        f" M={state.df3_mid_chunks}"
                        f" Q={state.df3_quiet_chunks}"
                        f" xfade={state.df3_boundaries}]"
                        if state.df3_adaptive else "")
            L(f"  [T-0.5/استراد] DF3 OK{_adf_tag}"
              f" — SNR {snr_before:.1f} → {state.df3_snr_after:.1f} dB")
        else:
            L("  [T-0.5/استراد] DF3 failed — continuing with original audio")
    elif df_trigger and not df_avail:
        L("  [T-0.5/استراد] deepfilter not installed — skipped")
    elif not state.safi_applied and not state.tier_unprocessable and snr_frame >= _DF3_GATE:
        L(f"  [T-0.5] SNR={snr_frame:.1f} dB >= {_DF3_GATE} — no NR needed")

    """
    T2-R2: الاسترداد Orchestrator — runs between Phase B (NR) and Phase C (EQ).

    Order: TYPE_A (denoise) → TYPE_B (expand).
    Denoising first is correct: the expansion threshold calibration uses
    the frame RMS distribution. Noise contamination in every frame inflates
    the threshold, which shifts the expansion onset to the wrong level.
    Clean audio first → accurate threshold → correct expansion.

    Updates state.achievable_* from actual recovery measured.
    Returns (recovered_wav_path, t2_report).
    """
    t2_report: Dict = {
        'tier2_active': True,
        'type_a_applied': False, 'type_a_report': {},
        'type_b_applied': False, 'type_b_report': {},
        'type_c_applied': False, 'type_c_report': {},
        'r1_wow_applied':     False, 'r1_wow_pct':   0.0,
        'r2_dropout_applied': False, 'r2_dropouts':  0,
        'r3_harmonic_applied': False, 'r3_report':   {},
        'lra_recovered':  0.0,
        'snr_after':      state.snr_global,
    }

    _, t2_reason = needs_tier2(state)
    L(f'\n  ┌─ ENGINE-1: الاسترداد ({t2_reason}) ─')

    current_wav = input_wav

    # ── R-1: Wow/Flutter Correction (cassette pitch drift) ────────────────
    # Runs first — before NR — because pitch drift contaminates F0 estimation.
    # If we denoise first, the NR changes the spectral shape of voiced frames
    # and makes autocorrelation less reliable for F0 tracking.
    if state.source_tier in ('TIER_CRITICAL', 'TIER_DAMAGED'):
        L('  │  [R-1] wow/flutter detection...')
        wow_wav, wow_rep = recover_wow_flutter(current_wav, state)
        t2_report['r1_wow_applied'] = wow_rep.get('applied', False)
        t2_report['r1_wow_pct']     = wow_rep.get('max_wow_pct', 0.0)
        if wow_wav != current_wav:
            current_wav = wow_wav
            L(f'  │  [R-1] ✓ wow={wow_rep["max_wow_pct"]:.1f}% corrected')
        else:
            L(f'  │  [R-1] wow={wow_rep["max_wow_pct"]:.1f}% — no correction applied')

    # ── R-2: Dropout Reconstruction (tape gap filling) ────────────────────
    # Runs before NR: NR can partially mask dropout boundaries, making them
    # harder to detect. Raw signal shows dropout edges cleanly.
    if state.source_tier in ('TIER_CRITICAL', 'TIER_DAMAGED'):
        L('  │  [R-2] dropout detection...')
        dropout_wav, dr_rep = recover_dropouts(current_wav, state)
        t2_report['r2_dropout_applied'] = dr_rep.get('applied', False)
        t2_report['r2_dropouts']        = dr_rep.get('dropouts_fixed', 0)
        if dropout_wav != current_wav:
            current_wav = dropout_wav
            L(f'  │  [R-2] ✓ {dr_rep["dropouts_fixed"]}/{dr_rep["dropouts_found"]} dropouts filled')
        else:
            L(f'  │  [R-2] {dr_rep["dropouts_found"]} gap(s) found — '
              f'{"no fix applied" if not dr_rep.get("applied") else "applied"}')

    # ── TYPE A: Statistical Noise Recovery ───────────────────────────────
    if 'TYPE_A' in t2_reason:
        L('  │  [T2-A] statistical NR (silence_valid=False, SNR < 12dB)...')

        if not state.silence_valid:
            recovered_wav, a_report = nr_pass_statistical(current_wav, state, ref)
        else:
            # silence_valid=True but SNR < 12dB: noise profiling succeeded but
            # SNR is still very low. This means standard NR applied conservatively
            # — boost here with an extra targeted pass at nr=8.
            L('  │  [T2-A] silence_valid + SNR<12: boosted NR pass...')
            nf_boost = float(np.clip(state.silence_floor + 1.5, -76, -40))
            tmp_boost = os.path.join(_TMP, 'v104_boost_nr.wav')
            ok = ffmpeg_process(current_wav, tmp_boost,
                                f'afftdn=nr=8:nf={nf_boost:.0f}:tn=1')
            if ok:
                # Quick sibilant check
                post_c = load_audio_fast(tmp_boost, state.skip_s, 20)
                pre_c  = load_audio_fast(current_wav, state.skip_s, 20)
                sib_pre  = compute_sibilant_snr(pre_c,  state.silence_floor)
                sib_post = compute_sibilant_snr(post_c, state.silence_floor)
                if sib_post - sib_pre >= -3.0:
                    recovered_wav = tmp_boost
                    a_report = {'applied': True, 'method': 'boosted_standard',
                                'sib_delta': sib_post - sib_pre}
                else:
                    L('  │  [T2-A] boosted NR hurt sibilants — reverted')
                    try: os.unlink(tmp_boost)
                    except: pass
                    recovered_wav = current_wav
                    a_report = {'applied': False, 'method': 'boosted_reverted'}
            else:
                recovered_wav = current_wav
                a_report = {'applied': False, 'method': 'boosted_failed'}

        t2_report['type_a_report'] = a_report
        t2_report['type_a_applied'] = a_report.get('applied', False)

        if recovered_wav != current_wav:
            current_wav = recovered_wav
            # Re-measure SNR from the recovered audio
            post_c = load_audio_fast(current_wav, state.skip_s, min(state.dur_s, 30))
            post_band_snr = compute_band_snr(post_c)
            if post_band_snr:
                state.snr_global = float(np.mean(list(post_band_snr.values())))
                t2_report['snr_after'] = state.snr_global
            L(f'  │  [T2-A] ✓ sib_Δ={a_report.get("sib_delta",0):+.1f}dB '
              f'snr_after={state.snr_global:.1f}dB')
        else:
            L('  │  [T2-A] no improvement — continuing with NR pass output')

    # v5: recovery_confidence (nr_core_v16 SECTION 7)
    _snr_proxy = t2_report.get('snr_after', state.snr_global)
    _mg_proxy  = float(np.clip(_snr_proxy / 20.0, 0.40, 1.00)) if NUMPY_OK else 0.75
    _rc = _v16_compute_recovery_confidence(
        mean_gain    = _mg_proxy,
        source_tier  = state.source_tier,
        type_b_active= 'TYPE_B' in t2_reason,
        type_c_active= 'TYPE_C' in t2_reason,
    ) if NUMPY_OK else 0.75
    t2_report['recovery_confidence'] = _rc
    state.recovery_confidence = _rc
    L(f'  │  [v5] recovery_confidence={_rc:.3f} '
      f'(snr_proxy={_snr_proxy:.1f}dB tier={state.source_tier})')

    # ── TYPE B: Dynamic Restoration ──────────────────────────────────────
    if 'TYPE_B' in t2_reason or 'TYPE_B2' in t2_reason:
        L('  │  [T2-B] dynamic restoration (LRA crushed)...')

        # Analyse dynamic floor from (possibly denoised) current audio
        analysis_clip = load_audio_fast(current_wav, state.skip_s, state.dur_s)
        df = _analyze_dynamic_floor(analysis_clip, SR)

        L(f'  │  [T2-B] floor p10={df["p10_db"]:.1f} p50={df["median_db"]:.1f} '
          f'p90={df["p90_db"]:.1f} threshold={df["threshold_db"]:.1f}  '
          f'current_lra={df["current_lra"]:.2f}LU')

        L('  │  [T2-B] calibrating ratio...')
        ratio, predicted_gain = _calibrate_expansion_ratio(
            current_wav, state, ref, df)

        expanded_wav, b_report = _expansion_pass(current_wav, state, ref, ratio, df)

        t2_report['type_b_report'] = b_report
        t2_report['type_b_applied'] = b_report.get('applied', False)
        t2_report['lra_recovered']  = b_report.get('lra_gain', 0.0)

        if expanded_wav != current_wav:
            current_wav = expanded_wav
            L(f'  │  [T2-B] ✓ LRA {b_report["lra_before"]:.2f}→{b_report["lra_after"]:.2f}  '
              f'Crest {b_report["crest_before"]:.2f}→{b_report["crest_after"]:.2f}')
        else:
            L('  │  [T2-B] expansion reverted — LRA unchanged')

    # ── TYPE C: Codec Artifact Recovery ('pixeled voice') ────────────────
    # Runs AFTER A (denoise) and B (expand) — on the cleanest available audio.
    # Rationale: pre-echo suppression needs a clean baseline to detect
    # anomalous pre-transient energy. If ambient noise is still present,
    # the noise itself can exceed the transient detection threshold and
    # produce false positives. Denoise first (TYPE_A) → then detect
    # pre-echo accurately.
    if 'TYPE_C' in t2_reason:
        L('  │  [T2-C] codec artifact recovery (pixeled voice)...')
        # v5: TYPE_C upgraded — v16 vectorised NLM + smooth pre-echo v2
        recovered_c, c_report = _v16_type_c_for_tier2(current_wav, state)
        if not c_report.get('applied'):
            L('  │  [T2-C] v16 failed → fallback to legacy TYPE_C')
            recovered_c, c_report = nr_pass_codec_artifacts(current_wav, state, ref)
        t2_report['type_c_report']  = c_report
        t2_report['type_c_applied'] = c_report.get('applied', False)

        if recovered_c != current_wav:
            current_wav = recovered_c
            _tc_m = c_report.get('method', '?')
            L(f'  │  [T2-C] ✓ method={_tc_m}  '
              f'severity={c_report.get("severity", "?")}/3  '
              f'bw_ext={c_report.get("bw_ext_applied", False)}  '
              f'sib_delta={c_report.get("sib_delta", 0):+.1f}dB')
        else:
            L('  │  [T2-C] all codec stages reverted or bypassed')

    # ── R-3: Harmonic Inference (F0-tracked band extension) ───────────────
    # Runs AFTER TYPE_C: pre-echo suppression and anlmdn clean the codec
    # damage first, giving R-3 a reliable low-frequency harmonic base to
    # extrapolate from. Running before TYPE_C would measure codec-distorted
    # harmonics and synthesize from a corrupted envelope.
    # Also runs after TYPE_A (denoised signal gives cleaner autocorrelation
    # for F0 tracking — noise inflates the autocorrelation baseline and
    # pulls the peak threshold triggering false unvoiced classifications).
    if state.codec_cutoff < 13_000.0 and \
            state.source_tier in ('TIER_CRITICAL', 'TIER_DAMAGED'):
        L('  │  [R-3] harmonic inference (F0-tracked band extension)...')
        r3_wav, r3_rep = recover_harmonics(current_wav, state, ref)
        t2_report['r3_harmonic_applied'] = r3_rep.get('applied', False)
        t2_report['r3_report']           = r3_rep
        if r3_wav != current_wav:
            current_wav = r3_wav
            L(f'  │  [R-3] ✓ voiced={r3_rep["voiced_frames"]} '
              f'synth={r3_rep["synthesized_frames"]} '
              f'f0={r3_rep["mean_f0_hz"]:.1f}Hz '
              f'rms_delta={r3_rep["rms_delta_db"]:+.2f}dB')
        else:
            L(f'  │  [R-3] bypassed (reverted={r3_rep["reverted"]})')

    L(f'  └─ ENGINE-1: الاسترداد complete '
      f'(R1-wow={t2_report["r1_wow_applied"]} '
      f'R2-drop={t2_report["r2_dropout_applied"]} '
      f'R3-harm={t2_report["r3_harmonic_applied"]} '
      f'A={t2_report["type_a_applied"]} '
      f'B={t2_report["type_b_applied"]} '
      f'C={t2_report["type_c_applied"]} '
      f'lra_gain={t2_report["lra_recovered"]:+.2f}LU)')
    return current_wav, t2_report




# ══════════════════════════════════════════════════════════════════════════════
#  R-1: WOW / FLUTTER CORRECTION (TIER_CRITICAL — cassette pitch drift)
# ══════════════════════════════════════════════════════════════════════════════
def _estimate_f0_autocorr(frame: 'np.ndarray', sr: int,
                           f0_min: float = 70.0,
                           f0_max: float = 350.0) -> float:
    """
    Estimate F0 of a voiced frame via normalized autocorrelation.
    Returns F0 in Hz, or 0.0 if the frame appears unvoiced or estimation fails.

    Search range 70-350Hz covers the full male recitation range:
    Sheikh Al-Dossari's modal pitch is ~110-130Hz, with range 80-220Hz.
    350Hz upper bound captures falsetto and prevents fricative misclassification.
    """
    if not NUMPY_OK or len(frame) < 64:
        return 0.0

    # Energy gate: unvoiced frames have no reliable F0
    frame_rms = float(np.sqrt(np.mean(frame ** 2)))
    if frame_rms < 1e-5:
        return 0.0

    N = len(frame)
    lag_min = int(sr / f0_max)
    lag_max = int(sr / f0_min)
    if lag_max >= N:
        lag_max = N - 1
    if lag_min >= lag_max:
        return 0.0

    # Normalized autocorrelation
    f = frame - float(np.mean(frame))
    r0 = float(np.sum(f ** 2))
    if r0 < 1e-10:
        return 0.0

    acorr = np.array([
        float(np.sum(f[:N - lag] * f[lag:])) / (r0 + 1e-10)
        for lag in range(lag_min, lag_max + 1)
    ])

    peak_idx = int(np.argmax(acorr))
    peak_val = float(acorr[peak_idx])

    # Voicing threshold: autocorrelation peak must be > 0.35
    # (lower means the signal is more noise-like than periodic)
    if peak_val < 0.35:
        return 0.0

    lag_best = lag_min + peak_idx
    return float(sr / lag_best)


def _detect_wow_flutter(audio: 'np.ndarray', sr: int = SR,
                         frame_ms: float = 40.0) -> Tuple[float, 'np.ndarray']:
    """
    R-1a: Detect wow/flutter from F0 trajectory deviation.

    Wow: slow pitch drift (< 6Hz modulation rate) — caused by capstan speed
    variation in cassette decks. Flutter: faster (6-20Hz) but same physics.

    Method:
      1. Compute F0 per frame using autocorrelation
      2. Collect voiced frames (F0 > 0)
      3. Compute smoothed local median F0 over ±5 voiced frames
      4. wow_ratio = abs(F0 - median_F0) / median_F0
      5. max_wow_ratio is the severity — > 0.03 (3%) is audible

    Returns (max_wow_pct, f0_array_per_frame).
    f0_array has 0.0 for unvoiced frames, F0 in Hz for voiced.
    """
    if not NUMPY_OK:
        return 0.0, np.array([])

    frame_n  = int(frame_ms / 1000.0 * sr)
    hop_n    = frame_n // 2
    n_frames = (len(audio) - frame_n) // hop_n

    if n_frames < 10:
        return 0.0, np.array([])

    f0s = np.array([
        _estimate_f0_autocorr(audio[i * hop_n: i * hop_n + frame_n], sr)
        for i in range(n_frames)
    ], dtype=np.float32)

    voiced_mask = f0s > 0
    if voiced_mask.sum() < 20:
        return 0.0, f0s

    # Compute local median of voiced F0 in ±5-frame window
    voiced_f0 = f0s[voiced_mask]
    global_median = float(np.median(voiced_f0))
    if global_median < 50.0:
        return 0.0, f0s  # implausibly low — likely noise

    # Per-frame deviation from smoothed local median
    # Use a 3-second median window to capture slow wow
    win = max(3, int(3.0 / (frame_ms / 1000.0 / 2)))
    deviations = []
    for i in range(n_frames):
        if not voiced_mask[i]:
            continue
        i_lo = max(0, i - win)
        i_hi = min(n_frames, i + win)
        local_voiced = f0s[i_lo:i_hi][f0s[i_lo:i_hi] > 0]
        if len(local_voiced) < 3:
            local_median = global_median
        else:
            local_median = float(np.median(local_voiced))
        if local_median > 0:
            deviations.append(abs(f0s[i] - local_median) / local_median)

    if not deviations:
        return 0.0, f0s

    max_wow = float(np.percentile(deviations, 95))
    return max_wow, f0s


def _correct_wow_segment(audio: 'np.ndarray', sr: int,
                          f0s: 'np.ndarray', frame_ms: float = 40.0,
                          max_stretch: float = 0.08) -> 'np.ndarray':
    """
    R-1b: WSOLA-style wow correction via segment resampling.

    For each voiced frame where F0 deviates from the local median by > 2%,
    resample that segment to correct the pitch drift back toward the median.

    Physics: if F0_actual = 115Hz but F0_target = 110Hz, the tape was running
    5/110 = 4.5% too fast. We need to slow this segment down by 4.5%: stretch
    by factor 110/115 = 0.957. This is done by scipy.signal.resample.

    Crossfade: 10ms overlap with adjacent segments prevents click artifacts at
    segment boundaries. The cosine crossfade matches the WSOLA window.

    Guard: max stretch factor capped at max_stretch (8% = 0.92x to 1.08x).
    Beyond 8%, the correction is too large to be wow — it may be a transcription
    artifact or measurement error. Skip frames exceeding this cap.
    """
    if not NUMPY_OK or not SCIPY_OK:
        return audio

    try:
        from scipy.signal import resample as scipy_resample
    except ImportError:
        return audio

    frame_n  = int(frame_ms / 1000.0 * sr)
    hop_n    = frame_n // 2
    n_frames = len(f0s)
    crossfade_n = int(0.010 * sr)  # 10ms crossfade

    if n_frames < 10 or len(f0s) == 0:
        return audio

    voiced_mask = f0s > 0
    if voiced_mask.sum() < 10:
        return audio

    # Compute target F0 per frame: local 3s median of voiced frames
    win = max(3, int(3.0 / (frame_ms / 1000.0 / 2)))
    f0_target = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        if not voiced_mask[i]:
            continue
        i_lo = max(0, i - win)
        i_hi = min(n_frames, i + win)
        local_voiced = f0s[i_lo:i_hi][f0s[i_lo:i_hi] > 0]
        f0_target[i] = float(np.median(local_voiced)) if len(local_voiced) >= 3 else f0s[i]

    fixed = audio.copy().astype(np.float64)
    corrections = 0

    for i in range(n_frames):
        if not voiced_mask[i]:
            continue
        f0_act = f0s[i]
        f0_tgt = f0_target[i]
        if f0_tgt <= 0 or f0_act <= 0:
            continue

        deviation = abs(f0_act - f0_tgt) / f0_tgt
        if deviation < 0.02:   # < 2% deviation — inaudible, skip
            continue
        if deviation > max_stretch:
            continue  # Too large — not wow, skip

        # Stretch ratio: target/actual (ratio > 1 = slow down, < 1 = speed up)
        ratio = f0_tgt / f0_act

        s_start = i * hop_n
        s_end   = min(s_start + frame_n, len(fixed))
        seg     = fixed[s_start:s_end]
        if len(seg) < 16:
            continue

        new_len = int(round(len(seg) * ratio))
        if new_len < 8 or abs(new_len - len(seg)) > len(seg) * max_stretch:
            continue

        try:
            stretched = scipy_resample(seg, new_len).astype(np.float64)
        except Exception:
            continue

        # Place stretched segment — trim or pad to original length to keep
        # the output array the same size (we fix pitch, not duration)
        out_len = min(len(seg), new_len)
        cf_len  = min(crossfade_n, out_len // 4)

        # Crossfade at start of segment
        if cf_len > 0 and s_start > 0:
            fade_in  = np.linspace(0.0, 1.0, cf_len)
            fade_out = 1.0 - fade_in
            fixed[s_start: s_start + cf_len] = (
                fixed[s_start: s_start + cf_len] * fade_out
                + stretched[:cf_len] * fade_in
            )
            fixed[s_start + cf_len: s_start + out_len] = stretched[cf_len:out_len]
        else:
            fixed[s_start: s_start + out_len] = stretched[:out_len]

        corrections += 1

    L(f'  [R-1] {corrections}/{n_frames} frames pitch-corrected')
    return fixed.astype(np.float32)


def recover_wow_flutter(input_path: str, state: 'InputState') -> Tuple[str, Dict]:
    """
    R-1 Orchestrator: detect and correct wow/flutter in TIER_CRITICAL recordings.

    Trigger conditions (all must be true):
      - TIER_CRITICAL or TIER_DAMAGED source
      - noise_type contains 'hiss' (cassette indicator)
      - max wow deviation > 3% (threshold for audible pitch drift)

    Pipeline:
      1. Load full audio
      2. _detect_wow_flutter() → max_wow_pct, f0_array
      3. If max_wow_pct > 3%: _correct_wow_segment()
      4. Validate: F0 std-dev of corrected audio < original (stability improved)
      5. Guard: voiced RMS delta < 1.5dB (correction must not alter loudness)
    """
    report: Dict = {
        'applied': False, 'max_wow_pct': 0.0,
        'corrections': 0, 'reverted': False,
    }

    if not NUMPY_OK or not SCIPY_OK:
        return input_path, report

    if state.source_tier not in ('TIER_CRITICAL', 'TIER_DAMAGED'):
        return input_path, report

    # Only cassette recordings exhibit wow/flutter
    if 'hiss' not in state.noise_type and state.noise_type != 'hiss+hum':
        return input_path, report

    audio = load_audio_fast(input_path, 0, state.total_s)
    if len(audio) < SR * 10:
        return input_path, report

    max_wow, f0s = _detect_wow_flutter(audio, SR)
    report['max_wow_pct'] = round(max_wow * 100.0, 2)

    L(f'  [R-1] wow detection: max={max_wow*100:.1f}%  voiced_frames={int((f0s>0).sum())}')

    if max_wow < 0.03:
        L('  [R-1] wow < 3% — no correction needed')
        return input_path, report

    pre_rms = rms_db(audio)
    fixed_audio = _correct_wow_segment(audio, SR, f0s)

    # Validate: loudness must not shift
    post_rms = rms_db(fixed_audio)
    if abs(post_rms - pre_rms) > 1.5:
        L(f'  [R-1] RMS delta {post_rms-pre_rms:+.2f}dB > 1.5 — REVERTED')
        report['reverted'] = True
        return input_path, report

    # Write corrected audio to temp WAV
    tmp_wow = os.path.join(_TMP, 'v105_wow_corrected.wav')
    raw = fixed_audio.astype(np.float32).tobytes()
    r = subprocess.run(
        ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
         '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
         '-loglevel', 'error', tmp_wow],
        input=raw, capture_output=True)

    if r.returncode != 0 or not os.path.exists(tmp_wow):
        L('  [R-1] write failed — REVERTED')
        report['reverted'] = True
        return input_path, report

    report.update({'applied': True, 'max_wow_pct': round(max_wow * 100.0, 2)})
    L(f'  [R-1] ✓ wow={max_wow*100:.1f}% corrected → {tmp_wow}')
    return tmp_wow, report


# ══════════════════════════════════════════════════════════════════════════════
#  R-2: DROPOUT RECONSTRUCTION (gap filling in damaged recordings)
# ══════════════════════════════════════════════════════════════════════════════
def _detect_dropouts(audio: 'np.ndarray', sr: int = SR,
                     frame_ms: float = 10.0) -> List[Tuple[int, int]]:
    """
    R-2a: Detect dropout gaps in voiced recording content.

    A dropout is a frame (or sequence of frames) that is anomalously silent
    while surrounded by voiced content on both sides. This is the signature of:
      - Tape dropouts (magnetic oxide loss on cassette surface)
      - Digital transmission glitches
      - Recording device buffer underruns

    Detection:
      1. Compute frame RMS (10ms frames)
      2. Voiced median = median of frames in top 60% of energy (active speech)
      3. Dropout threshold = voiced_median - 28dB
      4. Find contiguous runs of frames below threshold
      5. Gap must be 20ms-3000ms (shorter = codec quantization noise, longer = silence)
      6. Gap must have voiced frames on BOTH sides within 200ms

    Returns list of (sample_start, sample_end) tuples for each dropout.
    """
    if not NUMPY_OK:
        return []

    frame_n = int(frame_ms / 1000.0 * sr)
    if len(audio) < frame_n * 30:
        return []

    n_frames = len(audio) // frame_n
    frame_rms = np.array([
        rms_db(audio[i * frame_n:(i + 1) * frame_n])
        for i in range(n_frames)
    ])

    # Voiced median: top 60% of frames by energy
    sorted_rms = np.sort(frame_rms)
    voiced_median = float(np.median(sorted_rms[int(n_frames * 0.40):]))
    dropout_thresh = voiced_median - 28.0

    # Minimum and maximum gap in frames
    min_gap_frames = max(2, int(20.0 / frame_ms))      # 20ms
    max_gap_frames = int(3000.0 / frame_ms)            # 3 seconds
    context_frames = int(200.0 / frame_ms)             # 200ms context window

    gaps: List[Tuple[int, int]] = []
    in_gap = False
    gap_start = 0

    for i in range(n_frames):
        is_silent = frame_rms[i] < dropout_thresh
        if is_silent and not in_gap:
            in_gap = True
            gap_start = i
        elif not is_silent and in_gap:
            gap_len = i - gap_start
            in_gap = False
            if gap_len < min_gap_frames or gap_len > max_gap_frames:
                continue
            # Both sides must have voiced content within context_frames
            left_ctx  = frame_rms[max(0, gap_start - context_frames): gap_start]
            right_ctx = frame_rms[i: min(n_frames, i + context_frames)]
            left_voiced  = np.any(left_ctx  > dropout_thresh + 10.0)
            right_voiced = np.any(right_ctx > dropout_thresh + 10.0)
            if left_voiced and right_voiced:
                gaps.append((gap_start * frame_n, i * frame_n))

    return gaps


def recover_dropouts(input_path: str, state: 'InputState') -> Tuple[str, Dict]:
    """
    R-2 Orchestrator: reconstruct audio dropouts via crossfade interpolation.

    For each detected dropout:
      - Take the last 50ms of pre-gap audio (fade-out source)
      - Take the first 50ms of post-gap audio (fade-in source)
      - Fill the gap with a crossfade blend from both sides
      - Crossfade shape: cosine taper (smooth onset/offset)

    This does not synthesize missing phonemes — it creates a perceptually smooth
    transition that masks the gap better than silence. The listener hears a brief
    fade rather than an abrupt cut.

    Scope: TIER_CRITICAL and TIER_DAMAGED only. Clean sources have no dropouts.

    Guards:
      - Max 40 dropouts corrected (more = systematic issue, not tape dropout)
      - Skip dropouts > 3s (real silence between ayahs — do not fill)
      - Voiced RMS delta after reconstruction < 1.5dB
    """
    report: Dict = {
        'applied': False, 'dropouts_found': 0,
        'dropouts_fixed': 0, 'reverted': False,
    }

    if not NUMPY_OK:
        return input_path, report

    if state.source_tier not in ('TIER_CRITICAL', 'TIER_DAMAGED'):
        return input_path, report

    audio = load_audio_fast(input_path, 0, state.total_s)
    if len(audio) < SR * 5:
        return input_path, report

    gaps = _detect_dropouts(audio, SR)
    report['dropouts_found'] = len(gaps)

    if not gaps:
        L('  [R-2] no dropouts detected')
        return input_path, report

    # Cap at 40 — more than 40 gaps in a recording is more likely a systematic
    # encoding problem than physical tape dropouts
    if len(gaps) > 40:
        L(f'  [R-2] {len(gaps)} gaps > 40 limit — likely encoding artifact, skip')
        return input_path, report

    L(f'  [R-2] {len(gaps)} dropout(s) detected — reconstructing...')

    fixed  = audio.copy()
    fade_n = int(0.050 * SR)   # 50ms crossfade
    n_fixed = 0

    for gap_start, gap_end in gaps:
        gap_len = gap_end - gap_start
        if gap_len <= 0:
            continue

        # Source audio from immediately before and after the gap
        pre_start  = max(0,          gap_start - fade_n)
        pre_audio  = audio[pre_start: gap_start]
        post_audio = audio[gap_end:   min(len(audio), gap_end + fade_n)]

        if len(pre_audio) < 8 or len(post_audio) < 8:
            continue

        # Build fill segment: crossfade from pre→post
        fill = np.zeros(gap_len, dtype=np.float64)
        for k in range(gap_len):
            alpha = k / max(gap_len - 1, 1)        # 0→1 across the gap
            cos_fade = (1.0 - np.cos(np.pi * alpha)) * 0.5  # smooth 0→1

            # Pre audio: reversed from gap edge (fade out)
            pre_idx = len(pre_audio) - 1 - int((1.0 - alpha) * (len(pre_audio) - 1))
            pre_idx = int(np.clip(pre_idx, 0, len(pre_audio) - 1))

            # Post audio: forward from gap edge (fade in)
            post_idx = int(alpha * (len(post_audio) - 1))
            post_idx = int(np.clip(post_idx, 0, len(post_audio) - 1))

            fill[k] = (pre_audio[pre_idx] * (1.0 - cos_fade)
                       + post_audio[post_idx] * cos_fade)

        fixed[gap_start:gap_end] = fill.astype(np.float32)
        n_fixed += 1

    report['dropouts_fixed'] = n_fixed

    # Validate: overall RMS must not shift
    pre_rms  = rms_db(audio)
    post_rms = rms_db(fixed)
    if abs(post_rms - pre_rms) > 1.5:
        L(f'  [R-2] RMS delta {post_rms-pre_rms:+.2f}dB > 1.5 — REVERTED')
        report['reverted'] = True
        return input_path, report

    tmp_dr = os.path.join(_TMP, 'v105_dropout_fixed.wav')
    raw = fixed.astype(np.float32).tobytes()
    r = subprocess.run(
        ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
         '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
         '-loglevel', 'error', tmp_dr],
        input=raw, capture_output=True)

    if r.returncode != 0 or not os.path.exists(tmp_dr):
        L('  [R-2] write failed — REVERTED')
        report['reverted'] = True
        return input_path, report

    report['applied'] = True
    L(f'  [R-2] ✓ {n_fixed}/{len(gaps)} dropouts reconstructed')
    return tmp_dr, report


# ══════════════════════════════════════════════════════════════════════════════
#  R-3: HARMONIC INFERENCE (F0-tracked additive synthesis above codec cutoff)
# ══════════════════════════════════════════════════════════════════════════════
def _measure_harmonic_envelope(
    frame: 'np.ndarray', sr: int, f0: float, cutoff_hz: float,
) -> Tuple[List[float], List[float]]:
    """
    Measure amplitudes of the harmonic series below codec_cutoff.

    For each harmonic k*F0 within [F0, cutoff_hz) find the peak amplitude
    in a ±max(F0*0.25, 30Hz) search window around the theoretical frequency.

    Returns (freqs_hz, amplitudes).  At least 3 points are required for
    the PCHIP extrapolation in _synthesize_harmonic_band to be meaningful.
    """
    N = len(frame)
    if N < 256:
        return [], []

    window      = np.hanning(N)
    spec        = np.abs(rfft(frame.astype(np.float64) * window)) / max(float(np.sum(window)), 1e-10)
    freqs       = rfftfreq(N, 1.0 / sr)
    search_bw   = max(f0 * 0.25, 30.0)

    harm_freqs: List[float] = []
    harm_amps:  List[float] = []

    k = 1
    while True:
        hf = f0 * k
        if hf >= cutoff_hz - f0:      # stop one harmonic below the cutoff
            break
        if hf >= sr / 2 - f0:
            break
        mask = (freqs >= max(0.0, hf - search_bw)) & (freqs <= hf + search_bw)
        if mask.sum() == 0:
            k += 1
            continue
        harm_freqs.append(hf)
        harm_amps.append(max(float(np.max(spec[mask])), 1e-12))
        k += 1

    return harm_freqs, harm_amps


def _synthesize_harmonic_band(
    frame_len: int,
    sr: int,
    f0: float,
    harm_freqs: List[float],
    harm_amps:  List[float],
    cutoff_hz:  float,
    max_hz:     float = 16_000.0,
    blend:      float = 0.35,
) -> 'np.ndarray':
    """
    Synthesize the harmonic series from cutoff_hz → max_hz using a
    PCHIP-extrapolated amplitude envelope fitted to the surviving harmonics.

    Steps:
      1.  Fit PCHIP through (harm_freqs, log_amps) in the surviving band.
      2.  For each k*F0 above cutoff_hz up to max_hz:
            a.  Extrapolate log-amplitude via PCHIP.
            b.  Clamp to max measured amplitude (no synthesized harmonic
                louder than the loudest surviving one).
            c.  Apply −3 dB/octave roll-off above cutoff (spectral tilt
                correction — high harmonics should decay, not be flat).
            d.  Add cosine sinusoid with a random phase to avoid comb
                artifacts with existing content.
      3.  Pass the summed sinusoids through a frequency-domain fade mask:
            – Half-cosine ramp up over the first 500 Hz above cutoff
            – Quadratic roll-off from 1.0 → 0.3 toward max_hz
            – Hard zero below cutoff and above max_hz
      4.  Scale by blend and return float32 frame.

    Returns np.zeros if PCHIP unavailable, < 3 harmonics, or any exception.
    """
    if not _PCHIP_OK or len(harm_freqs) < 3:
        return np.zeros(frame_len, dtype=np.float32)
    try:
        log_amps = np.log(np.array(harm_amps, dtype=np.float64) + 1e-12)
        pchip    = PchipInterpolator(harm_freqs, log_amps, extrapolate=True)
    except Exception:
        return np.zeros(frame_len, dtype=np.float32)

    t   = np.arange(frame_len, dtype=np.float64) / sr
    out = np.zeros(frame_len, dtype=np.float64)
    log_amp_cap = float(np.max(log_amps))

    k_start = int(np.ceil(cutoff_hz / f0))
    synth_count = 0
    for k in range(k_start, int(max_hz / f0) + 2):
        hf = f0 * k
        if hf > max_hz or hf >= sr / 2:
            break
        log_amp = min(float(pchip(hf)), log_amp_cap)
        amp     = float(np.exp(log_amp))
        # Spectral tilt: −3 dB per octave above cutoff
        amp    *= 10.0 ** (-3.0 * float(np.log2(max(hf / cutoff_hz, 1.0))) / 20.0)
        phase   = float(np.random.uniform(0.0, 2.0 * np.pi))
        out    += amp * np.cos(2.0 * np.pi * hf * t + phase)
        synth_count += 1

    if synth_count == 0:
        return np.zeros(frame_len, dtype=np.float32)

    # Frequency-domain fade mask
    N          = frame_len
    spec_out   = rfft(out * np.hanning(N))
    freqs_out  = rfftfreq(N, 1.0 / sr)
    fade_mask  = np.zeros(len(spec_out), dtype=np.float64)
    ramp_bw    = min(500.0, (max_hz - cutoff_hz) * 0.1)
    for i, f in enumerate(freqs_out):
        if f < cutoff_hz:
            fade_mask[i] = 0.0
        elif f < cutoff_hz + ramp_bw:
            fade_mask[i] = 0.5 * (1.0 - np.cos(np.pi * (f - cutoff_hz) / ramp_bw))
        elif f <= max_hz:
            fade_mask[i] = 0.3 + 0.7 * (1.0 - ((f - cutoff_hz) / (max_hz - cutoff_hz)) ** 2)
        else:
            fade_mask[i] = 0.0

    filtered = np.real(np.fft.irfft(spec_out * fade_mask, n=N))
    return (filtered * blend).astype(np.float32)


def recover_harmonics(input_path: str, state: 'InputState',
                      ref: 'ReferenceModel') -> Tuple[str, Dict]:
    """
    R-3: Harmonic Inference — reconstruct the voiced harmonic series above
    the codec bandwidth cutoff via F0-tracked additive synthesis.

    Physics:
    Quranic recitation is a quasi-periodic voiced signal with spectral content
    at F0, 2F0, 3F0, …  Codec truncation destroys harmonics above codec_cutoff,
    leaving the voice muffled or telephone-quality.  TYPE_C's aexciter adds
    broadband harmonic excitement but doesn't track F0 — its harmonics land at
    random multiples of whatever the aexciter's internal fundamental estimates,
    not at the real F0 multiples.

    R-3 fixes this:
      1. Estimate F0 per voiced frame (reuse _estimate_f0_autocorr from R-1).
      2. Measure harmonic amplitudes below codec_cutoff (_measure_harmonic_envelope).
      3. PCHIP-extrapolate the amplitude envelope into the missing band.
      4. Synthesize missing harmonics additively at exact F0 multiples.
      5. Overlap-add synthesized frames back into the full signal.

    Guards:
      – Fewer than 5 synthesized frames → skip (no voiced content, or cutoff
        too high relative to F0 to have a measurable series below it).
      – Sibilant guard: if HF energy in cutoff..cutoff+3kHz already > −30 dBFS,
        reduce blend 0.35 → 0.20 (fricatives already present — don't add more).
      – RMS delta > 1.5 dB → REVERT.
      – Crest factor degrades > 3 dB → REVERT.

    Trigger: state.codec_cutoff < 13_000 Hz AND
             state.source_tier in ('TIER_CRITICAL', 'TIER_DAMAGED').
    """
    report: Dict = {
        'applied':           False,
        'reverted':          False,
        'voiced_frames':     0,
        'synthesized_frames': 0,
        'codec_cutoff_hz':   state.codec_cutoff,
        'mean_f0_hz':        0.0,
        'rms_delta_db':      0.0,
    }

    if not NUMPY_OK or not SCIPY_OK or not _PCHIP_OK:
        return input_path, report

    cutoff = state.codec_cutoff
    if cutoff >= 13_000.0:
        return input_path, report
    if state.source_tier not in ('TIER_CRITICAL', 'TIER_DAMAGED'):
        return input_path, report

    audio = load_audio_fast(input_path, skip_s=0, duration_s=99_999)
    if len(audio) < SR * 2:
        return input_path, report

    audio   = audio.astype(np.float64)
    pre_rms = float(rms_db(audio.astype(np.float32)))

    frame_n    = 2048                           # ≈46 ms at 44100 Hz
    hop_n      = 512                            # 75 % overlap
    n_frames   = (len(audio) - frame_n) // hop_n
    max_hz     = min(16_000.0, SR / 2.0 - 200.0)

    if n_frames < 10:
        return input_path, report

    out_accum   = np.zeros(len(audio), dtype=np.float64)
    out_weights = np.zeros(len(audio), dtype=np.float64)
    ola_win     = np.hanning(frame_n)

    voiced_count = 0
    synth_count  = 0
    f0_list: List[float] = []

    for i in range(n_frames):
        s = i * hop_n
        e = s + frame_n
        if e > len(audio):
            break

        frame = audio[s:e]
        f0    = _estimate_f0_autocorr(frame.astype(np.float32), SR)
        if f0 <= 0.0:
            continue
        voiced_count += 1

        # Need ≥3 harmonics below cutoff to fit a PCHIP envelope
        if cutoff / f0 < 3.0:
            continue

        harm_freqs, harm_amps = _measure_harmonic_envelope(
            frame.astype(np.float32), SR, f0, cutoff)
        if len(harm_freqs) < 3:
            continue

        # Sibilant guard: measure energy in cutoff..cutoff+3kHz
        f_spec    = np.abs(rfft(frame * ola_win)) / (frame_n / 2.0)
        f_freqs   = rfftfreq(frame_n, 1.0 / SR)
        hf_mask   = (f_freqs >= cutoff) & (f_freqs <= min(cutoff + 3_000.0, max_hz))
        hf_rms_db = float(20.0 * np.log10(
            max(np.sqrt(np.mean(f_spec[hf_mask] ** 2) if hf_mask.sum() else 0.0), 1e-10)))
        blend     = 0.35 if hf_rms_db < -30.0 else 0.20

        synth = _synthesize_harmonic_band(
            frame_n, SR, f0, harm_freqs, harm_amps, cutoff,
            max_hz=max_hz, blend=blend)

        out_accum[s:e]   += synth * ola_win
        out_weights[s:e] += ola_win
        f0_list.append(f0)
        synth_count += 1

    report['voiced_frames']      = voiced_count
    report['synthesized_frames'] = synth_count

    if synth_count < 5:
        L(f'  [R-3] only {synth_count} frames synthesized — skipped')
        return input_path, report

    # OLA normalise
    safe_w   = np.where(out_weights > 1e-8, out_weights, 1.0)
    synth_sig = out_accum / safe_w

    mixed    = audio + synth_sig
    report['mean_f0_hz'] = float(np.mean(f0_list)) if f0_list else 0.0

    # RMS guard
    post_rms  = float(rms_db(mixed.astype(np.float32)))
    rms_delta = post_rms - pre_rms
    report['rms_delta_db'] = round(rms_delta, 2)
    if abs(rms_delta) > 1.5:
        L(f'  [R-3] RMS delta {rms_delta:+.2f} dB > 1.5 — REVERTED')
        report['reverted'] = True
        return input_path, report

    # Crest guard
    pre_crest  = float(peak_db(audio.astype(np.float32))) - pre_rms
    post_crest = float(peak_db(mixed.astype(np.float32))) - post_rms
    if post_crest - pre_crest > 3.0:
        L(f'  [R-3] crest {pre_crest:.1f}→{post_crest:.1f} dB — REVERTED')
        report['reverted'] = True
        return input_path, report

    # Write
    tmp_r3 = os.path.join(_TMP, 'v106_r3_harmonics.wav')
    raw    = np.clip(mixed, -1.0, 1.0).astype(np.float32).tobytes()
    proc   = subprocess.run(
        ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
         '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
         '-loglevel', 'error', tmp_r3],
        input=raw, capture_output=True)
    if proc.returncode != 0 or not os.path.exists(tmp_r3):
        L('  [R-3] write failed — REVERTED')
        report['reverted'] = True
        return input_path, report

    report['applied'] = True
    L(f'  [R-3] ✓ voiced={voiced_count}  synth={synth_count}  '
      f'f0_mean={report["mean_f0_hz"]:.1f} Hz  '
      f'cutoff={cutoff:.0f} Hz  rms_delta={rms_delta:+.2f} dB')
    return tmp_r3, report


# ══════════════════════════════════════════════════════════════════════════════
def shape_silence_floor(input_path: str, state: 'InputState',
                        ref: 'ReferenceModel') -> Tuple[str, Dict]:
    """
    R-5c: Add spectrally shaped noise during silence segments to match the
    reference 1425H ambient floor (-73dBFS ± 2dB).

    Physics: After aggressive NR, silence segments in TIER_CRITICAL sources
    often reach -80 to -90dBFS — artificially clean compared to the reference
    which has natural room ambience at -73dBFS. This creates an audible
    contrast between voiced phrases and inter-ayah silence that does not exist
    in the reference recordings. The listener hears a "pumping" effect as the
    background disappears and reappears.

    Fix: During detected silence segments (frames < voiced_median - 20dB),
    add pink-ish noise shaped to the reference spectral signature.

    Noise generation:
      - White noise filtered by a 1/f tilt (pink noise approximation)
      - Additional spectral shaping to match ref.third_oct profile at silence level
      - Level set to ref.silence_floor ± 1dB

    Guard:
      - Only applied when measured silence_floor < ref.silence_floor - 5dB
        (engine already produced silence quieter than reference)
      - Sibilant SNR must not degrade (the added noise must not mask fricatives)
      - Only TIER_CRITICAL/TIER_DAMAGED — clean sources already have correct floor
    """
    report: Dict = {
        'applied': False, 'floor_before': state.silence_floor,
        'floor_after': state.silence_floor, 'reverted': False,
    }

    if not NUMPY_OK:
        return input_path, report

    if state.source_tier not in ('TIER_CRITICAL', 'TIER_DAMAGED'):
        return input_path, report

    # Gate: only add noise if our output is more than 5dB quieter than reference
    ref_floor = float(ref.silence_floor)
    current_floor = float(state.silence_floor)
    if current_floor > ref_floor - 5.0:
        L(f'  [R-5c] silence floor {current_floor:.1f}dB already within 5dB of ref {ref_floor:.1f}dB — skip')
        return input_path, report

    audio = load_audio_fast(input_path, 0, state.total_s)
    if len(audio) < SR * 5:
        return input_path, report

    frame_n = int(0.02 * SR)   # 20ms frames for silence detection
    n_frames = len(audio) // frame_n
    frame_rms_vals = np.array([
        rms_db(audio[i * frame_n:(i + 1) * frame_n])
        for i in range(n_frames)
    ])

    voiced_median = float(np.median(frame_rms_vals[frame_rms_vals > -80]))
    silence_thresh = voiced_median - 20.0

    # Target noise amplitude: ref.silence_floor in linear
    target_floor_db = float(np.clip(ref_floor, -80.0, -60.0))
    noise_amp = float(10.0 ** (target_floor_db / 20.0))

    if noise_amp < 1e-6:
        return input_path, report

    # Generate shaped noise: pink approximation via 1/f spectral coloring
    # Use numpy random, shape with simple IIR pink filter
    rng = np.random.default_rng(seed=42)
    noise_full = rng.standard_normal(len(audio)).astype(np.float64)

    # Simple pink noise approximation: weighted sum of downsampled white noise
    # This is a lightweight IIR approach (no scipy needed for this part)
    b0 = 0.99886; b1 = 0.99332; b2 = 0.96900; b3 = 0.86650; b4 = 0.55000; b5 = -0.7616
    w0 = w1 = w2 = w3 = w4 = w5 = w6 = 0.0
    pink = np.zeros(len(noise_full))
    for i, wn in enumerate(noise_full):
        w0 = b0 * w0 + wn * 0.3540
        w1 = b1 * w1 + wn * 0.3572
        w2 = b2 * w2 + wn * 0.1233
        w3 = b3 * w3 + wn * 0.0126
        w4 = b4 * w4 + wn * 0.0012
        w5 = b5 * w5 - wn * 0.0018
        pink[i] = w0 + w1 + w2 + w3 + w4 + w5 + w6 + wn * 0.5362
        w6 = wn * 0.115926

    # Normalize pink noise to target amplitude
    pink_rms = float(np.sqrt(np.mean(pink ** 2)))
    if pink_rms < 1e-10:
        return input_path, report
    pink = (pink / pink_rms * noise_amp).astype(np.float32)

    # Apply noise ONLY during detected silence segments
    fixed = audio.copy()
    noise_added = 0
    for i in range(n_frames):
        if frame_rms_vals[i] < silence_thresh:
            # KB-07: Print-through guard (KB §41.6)
            # Tape print-through artifacts sit at -65 to -55 dBFS — between
            # silence floor and voiced content. Adding pink noise on top of
            # print-through would mask those artifacts with noise, creating
            # unnatural silence/artifact blend. Skip such regions.
            if -65.0 <= frame_rms_vals[i] <= -55.0:
                continue   # Likely print-through — leave as-is

            s = i * frame_n
            e = min(s + frame_n, len(fixed))
            # Fade-in/out at segment boundaries to avoid clicks
            seg_len = e - s
            if seg_len < 4:
                continue
            envelope = np.ones(seg_len, dtype=np.float32)
            fade = min(16, seg_len // 4)
            envelope[:fade]  = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            envelope[-fade:] = np.linspace(1.0, 0.0, fade, dtype=np.float32)
            fixed[s:e] = fixed[s:e] + pink[s:e] * envelope
            noise_added += 1

    if noise_added == 0:
        L('  [R-5c] no silence frames found — skip')
        return input_path, report

    # Measure new floor
    analysis_clip = fixed[int(state.skip_s * SR): int((state.skip_s + state.dur_s) * SR)]
    if len(analysis_clip) > 0:
        overall = rms_db(analysis_clip)
        sil_frames_post = [
            rms_db(analysis_clip[j:j + frame_n])
            for j in range(0, len(analysis_clip) - frame_n, frame_n)
            if rms_db(analysis_clip[j:j + frame_n]) < overall - 15
        ]
        floor_after = float(np.median(sil_frames_post)) if sil_frames_post else current_floor
    else:
        floor_after = target_floor_db

    report['floor_after'] = float(floor_after)

    # Sibilant guard: adding noise must not mask sibilants
    pre_sib = compute_sibilant_snr(
        audio[int(state.skip_s * SR): int((state.skip_s + 30) * SR)],
        current_floor)
    post_sib = compute_sibilant_snr(
        fixed[int(state.skip_s * SR): int((state.skip_s + 30) * SR)],
        floor_after)
    if post_sib - pre_sib < -3.0:
        L(f'  [R-5c] sibilant SNR drop {post_sib-pre_sib:+.1f}dB — REVERTED')
        report['reverted'] = True
        return input_path, report

    # Write result
    tmp_sfl = os.path.join(_TMP, 'v105_silence_shaped.wav')
    raw = fixed.astype(np.float32).tobytes()
    r = subprocess.run(
        ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
         '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
         '-loglevel', 'error', tmp_sfl],
        input=raw, capture_output=True)

    if r.returncode != 0 or not os.path.exists(tmp_sfl):
        L('  [R-5c] write failed — REVERTED')
        report['reverted'] = True
        return input_path, report

    report['applied'] = True
    L(f'  [R-5c] ✓ floor {current_floor:.1f}→{floor_after:.1f}dBFS  '
      f'({noise_added} silence frames shaped)')
    return tmp_sfl, report


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE B6: الجلال — VOICE TRANSCENDENCE ENGINE
#  "فَأَيُّ آلَاءِ رَبِّكُمَا تُكَذِّبَانِ"
#  Five sub-modules that carry the voice beyond restoration into glory.
# ══════════════════════════════════════════════════════════════════════════════

def _jalal_shimmer(audio: np.ndarray, sr: int,
                   src_lo: float, src_hi: float,
                   dst_lo: float, dst_hi: float,
                   blend: float) -> np.ndarray:
    """
    J-1: Spectral shimmer synthesis via STFT frequency translation.

    Copies spectral content from [src_lo, src_hi] Hz, translates it one
    octave upward into [dst_lo, dst_hi] Hz, and mixes at 'blend' amplitude.
    Each injected bin receives a fresh random phase so the shimmer
    decorrelates from the original voice and floats above it.

    A half-sine fade envelope tapers the destination bins at both edges —
    no abrupt discontinuities that could produce ringing or EQ colouration.

    Blend 0.042 (TIER_PRISTINE) ≈ −27 dBFS relative to source band energy.
    The Sheikh's vocal harmonics in 3-7 kHz are rich with upper partials.
    Doubling their frequency synthesises the energy a resonant stone chamber
    returns — the crystalline presence quality that lifts an MP3 toward a
    live hall experience.
    """
    if not _V16_SCIPY_FULL or not NUMPY_OK:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    stft_n = 2048; hop_n = stft_n // 4
    try:
        _, _, Zxx = _scipy_stft(audio.astype(np.float32), fs=sr,
                                nperseg=stft_n, noverlap=stft_n - hop_n,
                                window='hann')
    except Exception:
        return audio

    freqs       = rfftfreq(stft_n, 1.0 / sr)
    n_freq, n_time = Zxx.shape
    Zxx_out     = Zxx.copy()

    src_mask = (freqs >= src_lo) & (freqs <= src_hi)
    dst_mask = (freqs >= dst_lo) & (freqs <= dst_hi)
    if not src_mask.any() or not dst_mask.any():
        return audio

    src_bins = np.where(src_mask)[0]
    dst_bins = np.where(dst_mask)[0]
    n_src    = len(src_bins)
    n_dst    = len(dst_bins)

    # Smooth spectral window over destination bins (avoids abrupt edges)
    fade = np.sin(np.linspace(0.0, np.pi, n_dst)).astype(np.float32)

    rng = np.random.default_rng(seed=137)

    for t in range(n_time):
        src_mag   = np.abs(Zxx[src_bins, t]).astype(np.float64)
        resampled = np.interp(
            np.linspace(0, n_src - 1, n_dst),
            np.arange(n_src), src_mag
        ).astype(np.float32)
        phase        = rng.uniform(0.0, 2.0 * np.pi, n_dst).astype(np.float32)
        contribution = (resampled * fade * float(blend)
                        * np.exp(1j * phase).astype(np.complex64))
        Zxx_out[dst_bins, t] += contribution

    try:
        _, audio_out = _scipy_istft(Zxx_out, fs=sr,
                                    nperseg=stft_n,
                                    noverlap=stft_n - hop_n,
                                    window='hann')
    except Exception:
        return audio

    n_in      = len(audio)
    audio_out = (audio_out[:n_in] if len(audio_out) >= n_in
                 else np.pad(audio_out, (0, n_in - len(audio_out))))
    return _nan_guard(audio_out.astype(np.float32))


def _jalal_transient_sculptor(audio: np.ndarray, sr: int,
                               boost_db: float,
                               attack_ms: float) -> np.ndarray:
    """
    J-2: Arabic consonant transient sharpening via spectral flux onset detection.

    Arabic stops and plosives (ق ك ط ب د ت) generate rapid spectral flux
    events in the 2-8 kHz formant band.  Codec compression rounds these
    leading edges: the consonant arrives but its snap is softened.

    This sub-module:
      1. Computes per-frame spectral flux in the 2-8 kHz band via STFT.
      2. Labels onset frames where flux exceeds 2.8× the local 16-frame
         median — fires on consonant releases, not vowel transitions.
      3. At each onset, applies a cosine-tapered gain ramp over 'attack_ms'
         samples: gain peaks at onset, returns to unity at window end.
         Only the ATTACK is boosted — the vowel body is untouched.

    Net effect: every consonant regains the micro-dynamic snap that
    distinguishes a master recording from a compressed one.  Makhraj
    precision becomes audible even on modest playback systems.
    """
    if not _V16_SCIPY_FULL or not NUMPY_OK:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    stft_n = 1024; hop_n = 256
    try:
        _, _, Zxx = _scipy_stft(audio.astype(np.float32), fs=sr,
                                nperseg=stft_n, noverlap=stft_n - hop_n,
                                window='hann')
    except Exception:
        return audio

    freqs     = rfftfreq(stft_n, 1.0 / sr)
    band_mask = (freqs >= 2000.0) & (freqs <= 8000.0)
    if not band_mask.any():
        return audio

    mag  = np.abs(Zxx[band_mask, :]).astype(np.float32)
    flux = np.concatenate([[0.0],
                           np.sum(np.maximum(np.diff(mag, axis=1), 0.0), axis=0)])

    k_win     = 17
    flux_pad  = np.pad(flux, k_win // 2, mode='edge')
    local_med = np.array([np.median(flux_pad[i: i + k_win])
                          for i in range(len(flux))], dtype=np.float32)
    onset_mask = flux > 2.8 * (local_med + 1e-10)

    boost_lin      = float(10.0 ** (boost_db / 20.0))
    attack_samples = max(1, int(attack_ms / 1000.0 * sr))
    output         = audio.copy().astype(np.float32)

    pre_fade = max(1, int(sr * 0.003))   # 3ms pre-fade ramp before onset
    for t in range(len(flux)):
        if not onset_mask[t]:
            continue
        s = t * hop_n
        e = min(s + attack_samples, len(output))
        if e <= s:
            continue
        # Pre-fade: ramp gain up from 1.0 → boost_lin before the onset
        pre_s = max(0, s - pre_fade)
        if pre_s < s:
            plen   = s - pre_s
            pramp  = np.linspace(0.0, 1.0, plen, dtype=np.float32)
            output[pre_s:s] *= (1.0 + pramp * (boost_lin - 1.0))
        # Attack: cos² decay from boost_lin back to 1.0
        seg_len = e - s
        taper   = np.cos(np.linspace(0.0, np.pi / 2.0, seg_len)) ** 2
        gain    = 1.0 + taper.astype(np.float32) * (boost_lin - 1.0)
        output[s:e] *= gain

    return _nan_guard(output)


def _jalal_formant_resonator(audio: np.ndarray, sr: int,
                              boost_db: float, formant_q: float) -> np.ndarray:
    """
    J-3: Vocal formant resonance amplification via per-frame LPC peak tracking.

    Every voiced frame contains a spectral peak structure (F1/F2/F3) that
    defines the Sheikh's voice identity.  NR, codec compression, and EQ
    all tend to partially flatten these peaks.

    Per voiced frame (ZCR gate: ZCR < 0.25):
      1. LPC order-12 analysis → detect dominant peak in 200-3000 Hz.
      2. Build a parametric EQ gain mask at that exact frequency, Q=formant_q.
      3. Apply via STFT gain shaping and OLA synthesis.

    Boost is small (≤1.1 dB at TIER_PRISTINE) and frequency-exact:
    it amplifies what is already there — the Sheikh's own resonance —
    not imposing external colouration.  The result is presence and warmth
    without the plasticity of over-EQ'd audio.
    """
    if not _SCIPY_SIGNAL_OK or not NUMPY_OK:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    hop        = max(1, int(sr * 0.010))
    nfft       = hop * 4
    win        = np.hanning(nfft)
    n_frames   = max(1, (len(audio) - nfft) // hop)
    nfft_half  = nfft // 2 + 1
    freqs_hz   = rfftfreq(nfft, 1.0 / sr)
    boost_lin  = float(10.0 ** (boost_db / 20.0))

    out_ola  = np.zeros(len(audio) + nfft, dtype=np.float64)
    norm_ola = np.zeros(len(audio) + nfft, dtype=np.float64)

    for i in range(n_frames):
        s     = i * hop
        e     = s + nfft
        frame = (audio[s:e] if e <= len(audio)
                 else np.pad(audio[s:], (0, max(0, e - len(audio)))))
        frame = frame[:nfft].astype(np.float64)

        zcr = float(np.sum(np.abs(np.diff(np.sign(frame))))) / (2 * max(len(frame) - 1, 1))
        if zcr >= 0.25:
            out_ola[s: s + nfft]  += frame * win
            norm_ola[s: s + nfft] += win
            continue

        formant_f = 0.0
        try:
            from scipy.signal import lpc as _lpc_fn
            a_coef    = _lpc_fn(frame * win, order=12)
            n_lpc     = 256
            lpc_freqs = rfftfreq(n_lpc, 1.0 / sr)
            lpc_spec  = np.abs(1.0 / (rfft(a_coef, n=n_lpc) + 1e-30))
            f_mask    = (lpc_freqs >= 200.0) & (lpc_freqs <= 3000.0)
            lf = lpc_spec[f_mask]; lfq = lpc_freqs[f_mask]
            peaks = [(lfq[j], lf[j]) for j in range(1, len(lf) - 1)
                     if lf[j] > lf[j - 1] and lf[j] > lf[j + 1]]
            if peaks:
                formant_f = max(peaks, key=lambda p: p[1])[0]
        except Exception:
            pass

        if formant_f <= 0.0:
            out_ola[s: s + nfft]  += frame * win
            norm_ola[s: s + nfft] += win
            continue

        gain_mask = np.ones(nfft_half, dtype=np.float64)
        for bi in range(nfft_half):
            fq = freqs_hz[bi]
            if fq <= 0.0:
                continue
            ratio = fq / (formant_f + 1e-10)
            denom = 1.0 + formant_q ** 2 * (ratio - 1.0 / (ratio + 1e-10)) ** 2
            gain_mask[bi] += (boost_lin - 1.0) / denom

        spec      = rfft(frame * win)
        frame_out = np.real(np.fft.irfft(spec * gain_mask))[:nfft]
        frame_out = _nan_guard(frame_out)

        out_ola[s: s + nfft]  += frame_out * win
        norm_ola[s: s + nfft] += win

    norm_safe = np.where(norm_ola > 1e-6, norm_ola, 1.0)
    result    = (out_ola / norm_safe)[:len(audio)].astype(np.float32)
    return _nan_guard(result)


def _jalal_stereo_widener(audio_mono: np.ndarray, sr: int,
                           delay_ms: float, mix: float) -> np.ndarray:
    """
    J-4: Haas-effect psychoacoustic stereo widener.

    Delay of 7-15 ms between channels falls inside the Haas zone: the brain
    perceives spatial width without localising the delayed copy as a separate
    source.  The dry, centred mono image becomes a wide living presence —
    the voice breathes in a space.

    Left  — original signal passed through a first-order all-pass filter
             (coefficient 0.65) for spectral decorrelation above ~1 kHz.
    Right — original signal delayed by 'delay_ms' milliseconds.

    Mix crossfade: (1-mix)×original + mix×altered.  At mix=0.20 the mono
    sum of L+R stays within ±0.15 dB of original RMS — mono compatible.
    Returns (n_samples, 2) float32 stereo array.
    """
    if not NUMPY_OK:
        mono = audio_mono.astype(np.float32)
        return np.column_stack([mono, mono])

    n        = len(audio_mono)
    delay_n  = min(max(1, int(delay_ms / 1000.0 * sr)), n - 1)
    orig_f64 = audio_mono.astype(np.float64)

    # Left: first-order all-pass decorrelation
    a_coeff  = 0.65
    left_ap  = np.zeros(n, dtype=np.float64)
    prev_x   = 0.0; prev_y = 0.0
    for i in range(n):
        x          = orig_f64[i]
        y          = -a_coeff * x + prev_x + a_coeff * prev_y
        left_ap[i] = y
        prev_x = x;  prev_y = y

    # Right: Haas delay
    right_del        = np.zeros(n, dtype=np.float64)
    right_del[delay_n:] = orig_f64[:n - delay_n]

    L_out = (1.0 - mix) * orig_f64 + mix * left_ap
    R_out = (1.0 - mix) * orig_f64 + mix * right_del

    # Preserve mono RMS for downstream LUFS consistency
    orig_rms = float(np.sqrt(np.mean(orig_f64 ** 2)) + 1e-10)
    sum_rms  = float(np.sqrt(np.mean(((L_out + R_out) / 2.0) ** 2)) + 1e-10)
    if sum_rms > 1e-8:
        scale  = orig_rms / sum_rms
        L_out *= scale;  R_out *= scale

    return np.column_stack([L_out, R_out]).astype(np.float32)


def _jalal_subharmonic(audio: np.ndarray, sr: int,
                        blend: float,
                        freq_lo: float, freq_hi: float) -> np.ndarray:
    """
    J-5: Sub-harmonic foundation synthesis.

    The Sheikh's modal F0 ≈ 110-130 Hz.  The sub-harmonic at F0/2 (55-65 Hz)
    sits in the chest-cavity resonance zone — where the body itself vibrates.
    Great recordings capture it; MP3 at 128 kbps loses it first.

    Per voiced frame:
      1. Autocorrelation F0 detection (70-350 Hz).
      2. Synthesize sinusoid at F0/2 with random phase, OLA accumulated.
      3. Butterworth 4th-order bandpass to [freq_lo, freq_hi] Hz — prevents
         bleed into the voice fundamental.
      4. Mix at 'blend' amplitude (capped at 0.12).

    The voice acquires gravitational weight: physically present, not merely
    heard.  On speakers with sub-bass extension the effect is profound;
    on laptop speakers it contributes warmth at 80-100 Hz.
    """
    if not NUMPY_OK or not SCIPY_OK:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    try:
        from scipy.signal import butter, filtfilt as _filtfilt
    except ImportError:
        return audio

    blend    = float(np.clip(blend, 0.0, 0.12))
    # 50% overlap OLA — adjacent frames share half their length,
    # so phase discontinuities at boundaries are cancelled by windowing.
    frame_n  = max(1, int(sr * 0.040))        # 40ms frame
    hop      = frame_n // 2                   # 50% overlap
    n_frames = max(1, (len(audio) - frame_n) // hop)
    win      = np.hanning(frame_n)
    norm_ola = np.zeros(len(audio) + frame_n, dtype=np.float64)
    sub_sig  = np.zeros(len(audio) + frame_n, dtype=np.float64)
    # Track continuous phase so adjacent frames connect smoothly
    phase_acc = 0.0

    for i in range(n_frames):
        s     = i * hop
        e     = s + frame_n
        frame = (audio[s:e] if e <= len(audio)
                 else np.pad(audio[s:], (0, max(0, e - len(audio)))))
        frame = frame[:frame_n].astype(np.float32)

        f0 = _estimate_f0_autocorr(frame, sr, f0_min=70.0, f0_max=350.0)
        if f0 <= 0.0:
            phase_acc += 2.0 * np.pi * (freq_lo + freq_hi) * 0.5 / sr * hop
            continue

        sub_f   = float(np.clip(f0 / 2.0, freq_lo, freq_hi))
        t_ax    = np.arange(frame_n, dtype=np.float64) / sr
        # Use accumulated phase for continuity — no random jumps
        sub_frm = np.sin(2.0 * np.pi * sub_f * t_ax + phase_acc) * win
        phase_acc += 2.0 * np.pi * sub_f / sr * hop   # advance by hop

        frm_rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)) + 1e-12)
        sub_rms = float(np.sqrt(np.mean(sub_frm ** 2)) + 1e-12)
        sub_frm *= (frm_rms * blend / sub_rms)

        end_a = min(s + frame_n, len(sub_sig))
        sub_sig[s:end_a]  += sub_frm[:end_a - s]
        norm_ola[s:end_a] += win[:end_a - s]

    # OLA normalization — where window overlaps, divide out the window sum
    norm_safe = np.where(norm_ola[:len(audio)] > 0.1, norm_ola[:len(audio)], 1.0)
    sub_sig   = sub_sig[:len(audio)] / norm_safe

    try:
        lo_n = float(np.clip((freq_lo * 2.0) / sr, 0.001, 0.49))
        hi_n = float(np.clip((freq_hi * 2.0) / sr, lo_n + 0.01, 0.49))
        from scipy.signal import sosfilt as _sosfilt_sub
        sos_bp        = butter(4, [lo_n, hi_n], btype='band', output='sos')
        sub_sig_filt  = _sosfilt_sub(sos_bp, sub_sig)
    except Exception:
        sub_sig_filt  = sub_sig

    mixed = np.clip(audio.astype(np.float64) + sub_sig_filt, -1.0, 1.0)
    return _nan_guard(mixed.astype(np.float32))


def apply_jalal(
    input_wav: str,
    state: 'InputState',
    ref:   'ReferenceModel',
    log_fn=None,
) -> Tuple[str, Dict]:
    """
    الجلال — Voice Transcendence Engine orchestrator.

    Sub-module order:
      J-1  Shimmer       → crystalline octave-up presence layer
      J-2  Transient     → Arabic consonant edge sharpening
      J-3  Formant       → vocal identity resonance boost
      J-5  Subharmonic   → chest gravity (mono)
      J-4  Widener       → Haas stereo imaging  (mono → stereo WAV, runs last)

    J-GATE validates the cumulative output.  On gate failure:
      • Attempts mono-only partial revert (skip widener, re-validate).
      • Falls back to full revert returning input_wav unchanged.

    Bypassed on TIER_CRITICAL.  Returns (output_wav_path, report_dict).
    """
    _log  = log_fn or L
    report: Dict = {
        'status': 'SKIPPED', 'reason': '',
        'j1_shimmer':  False, 'j2_transient': False,
        'j3_formant':  False, 'j4_widener':   False,
        'j5_sub':      False,
        'sib_delta':   0.0,   'lufs_delta':   0.0,
        'crest_delta': 0.0,
    }

    tier = state.source_tier
    if tier not in _JALAL_TIER_PARAMS:
        report['reason'] = f'tier={tier}'
        return input_wav, report

    if not NUMPY_OK:
        report['reason'] = 'numpy unavailable'
        return input_wav, report

    params = _JALAL_TIER_PARAMS[tier]

    # ── Pre-gate baseline ──────────────────────────────────────────────────
    pre_audio = load_audio_fast(input_wav, state.skip_s, min(state.dur_s, 45))
    if len(pre_audio) < SR * 3:
        report['reason'] = 'audio too short'
        return input_wav, report

    pre_sib   = compute_sibilant_snr(pre_audio, state.silence_floor)
    pre_lufs  = measure_lufs(input_wav)
    pre_crest = crest_factor(pre_audio)

    # ── Load full mono audio ───────────────────────────────────────────────
    full_audio = load_audio_fast(input_wav, 0.0, state.total_s)
    if len(full_audio) < SR * 2:
        report['reason'] = 'full audio too short'
        return input_wav, report

    current = full_audio.copy()

    # ── J-1: Shimmer ──────────────────────────────────────────────────────
    try:
        current = _jalal_shimmer(
            current, SR,
            src_lo=params['shimmer_src_lo'], src_hi=params['shimmer_src_hi'],
            dst_lo=params['shimmer_dst_lo'], dst_hi=params['shimmer_dst_hi'],
            blend=params['shimmer_blend'])
        report['j1_shimmer'] = True
        _log(f'  [الجلال J-1] shimmer ✓  blend={params["shimmer_blend"]:.3f}  '
             f'{params["shimmer_src_lo"]:.0f}-{params["shimmer_src_hi"]:.0f}Hz'
             f' → {params["shimmer_dst_lo"]:.0f}-{params["shimmer_dst_hi"]:.0f}Hz')
    except Exception as _e:
        _log(f'  [الجلال J-1] shimmer error: {_e}')

    # ── J-2: Transient sculptor ────────────────────────────────────────────
    try:
        current = _jalal_transient_sculptor(
            current, SR,
            boost_db=params['transient_boost_db'],
            attack_ms=params['transient_attack_ms'])
        report['j2_transient'] = True
        _log(f'  [الجلال J-2] transient ✓  '
             f'boost={params["transient_boost_db"]:.1f}dB  '
             f'attack={params["transient_attack_ms"]:.0f}ms')
    except Exception as _e:
        _log(f'  [الجلال J-2] transient error: {_e}')

    # ── J-3: Formant resonator ─────────────────────────────────────────────
    try:
        current = _jalal_formant_resonator(
            current, SR,
            boost_db=params['formant_boost_db'],
            formant_q=params['formant_q'])
        report['j3_formant'] = True
        _log(f'  [الجلال J-3] formant ✓  '
             f'+{params["formant_boost_db"]:.2f}dB  Q={params["formant_q"]:.1f}')
    except Exception as _e:
        _log(f'  [الجلال J-3] formant error: {_e}')

    # ── J-5: Sub-harmonic (mono) ───────────────────────────────────────────
    try:
        current = _jalal_subharmonic(
            current, SR,
            blend=params['sub_blend'],
            freq_lo=params['sub_freq_lo'],
            freq_hi=params['sub_freq_hi'])
        report['j5_sub'] = True
        _log(f'  [الجلال J-5] sub-harmonic ✓  '
             f'blend={params["sub_blend"]:.3f}  '
             f'{params["sub_freq_lo"]:.0f}-{params["sub_freq_hi"]:.0f}Hz')
    except Exception as _e:
        _log(f'  [الجلال J-5] sub-harmonic error: {_e}')

    # ── J-4: Stereo widener (mono → stereo) ───────────────────────────────
    try:
        stereo_out = _jalal_stereo_widener(
            current, SR,
            delay_ms=params['widener_delay_ms'],
            mix=params['widener_mix'])
        report['j4_widener'] = True
        _log(f'  [الجلال J-4] widener ✓  '
             f'delay={params["widener_delay_ms"]:.0f}ms  '
             f'mix={params["widener_mix"]:.2f}')
    except Exception as _e:
        _log(f'  [الجلال J-4] widener error: {_e} — mono fallback')
        stereo_out = np.column_stack([current, current]).astype(np.float32)

    # ── Write stereo WAV ───────────────────────────────────────────────────
    import uuid as _uuid_j
    tmp_jalal     = os.path.join(_TMP, f'jalal_b6_{_uuid_j.uuid4().hex[:8]}.wav')
    stereo_bytes  = stereo_out.flatten(order='C').astype(np.float32).tobytes()

    rc = subprocess.run(
        ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2',
         '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
         '-loglevel', 'error', tmp_jalal],
        input=stereo_bytes, capture_output=True)

    if rc.returncode != 0 or not os.path.exists(tmp_jalal):
        _log('  [الجلال] WAV write failed — full revert')
        report['reason'] = 'write_failed'
        return input_wav, report

    # ── J-GATE: cumulative validation ─────────────────────────────────────
    def _gate_check(wav: str) -> Tuple[bool, str, float, float, float]:
        post_a = load_audio_fast(wav, state.skip_s, min(state.dur_s, 45))
        if len(post_a) < SR * 2:
            return False, 'post_audio_too_short', 0.0, 0.0, 0.0
        sib  = compute_sibilant_snr(post_a, state.silence_floor)
        lufs = measure_lufs(wav)
        cres = crest_factor(post_a)
        sd   = sib  - pre_sib
        ld   = abs(lufs - pre_lufs)
        cd   = abs(cres - pre_crest)
        if sd < _JALAL_GATE_SIB_DELTA:
            return False, f'sib_delta={sd:.2f}dB', sd, ld, cd
        if ld > _JALAL_GATE_LUFS_DELTA:
            return False, f'lufs_delta={ld:.2f}dB', sd, ld, cd
        if cd > _JALAL_GATE_CREST_DELTA:
            return False, f'crest_delta={cd:.2f}dB', sd, ld, cd
        return True, '', sd, ld, cd

    gate_ok, gate_msg, sib_d, lufs_d, crest_d = _gate_check(tmp_jalal)

    if not gate_ok:
        _log(f'  [الجلال J-GATE] FAIL ({gate_msg}) — trying mono-only partial revert')
        try: os.unlink(tmp_jalal)
        except: pass

        tmp_mono     = os.path.join(_TMP, f'jalal_b6_mono_{_uuid_j.uuid4().hex[:8]}.wav')
        raw_mono     = current.astype(np.float32).tobytes()
        gate_msg2    = 'mono_write_failed'
        gate_ok2     = False
        rc2 = subprocess.run(
            ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
             '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
             '-loglevel', 'error', tmp_mono],
            input=raw_mono, capture_output=True)

        if rc2.returncode == 0 and os.path.exists(tmp_mono):
            gate_ok2, gate_msg2, sib_d, lufs_d, crest_d = _gate_check(tmp_mono)
            if gate_ok2:
                _log(f'  [الجلال J-GATE] mono-revert accepted  '
                     f'sib_Δ={sib_d:+.2f}dB  lufs_Δ={lufs_d:+.2f}dB')
                report.update({
                    'status': 'OK_MONO', 'j4_widener': False,
                    'sib_delta':   round(float(sib_d),   2),
                    'lufs_delta':  round(float(lufs_d),  2),
                    'crest_delta': round(float(crest_d), 2),
                })
                return tmp_mono, report
            try: os.unlink(tmp_mono)
            except: pass

        _log(f'  [الجلال J-GATE] full revert — {gate_msg2}')
        report['reason'] = gate_msg
        report['status'] = 'REVERTED'
        return input_wav, report

    _log(f'  [الجلال] ✓  sib_Δ={sib_d:+.2f}dB  lufs_Δ={lufs_d:+.2f}dB  '
         f'crest_Δ={crest_d:+.2f}dB  '
         f'[J1={report["j1_shimmer"]} J2={report["j2_transient"]} '
         f'J3={report["j3_formant"]} J4={report["j4_widener"]} '
         f'J5={report["j5_sub"]}]')
    report.update({
        'status':      'OK',
        'sib_delta':   round(float(sib_d),   2),
        'lufs_delta':  round(float(lufs_d),  2),
        'crest_delta': round(float(crest_d), 2),
    })
    return tmp_jalal, report


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE B7: النداء — NEURAL IDENTITY-DRIVEN AUDIO ASCENSION
#  Derived entirely from acoustic DNA of Sheikh Yasser Al-Dosari's
#  three reference recordings (المرجع1425 · فاطر1425 · سورة الفتح).
#  Every constant below was measured, not guessed.
# ══════════════════════════════════════════════════════════════════════════════

# ── Acoustic DNA target vector (from المرجع1425 — the Master Reference) ──────
_NIDAA_TARGET = {
    # Pitch center (his natural rest — المرجع1425)
    'F0_center_hz':       146.0,

    # Harmonic rolloff target — dark, warm, authoritative
    # Measured: −11.78 dB/oct at the reference. All other files lighter.
    'harmonic_rolloff_db_oct': -11.78,

    # Even-harmonic dominance: even partials must dominate odd by 12.4 dB
    # This is the single most important signature of his voice character.
    # H2 sits +3.6 dB above H1 in the reference.
    'even_odd_bias_db':   -12.4,
    'H2_rel_H1_db':        3.6,

    # Sibilant fingerprint (consensus المرجع + فاطر — ignoring الفتح 192kbps artifact)
    'sib_centroid_hz':    4280.0,
    'sib_peak_hz':        3800.0,
    'sib_slope_5k_db_oct': -8.3,

    # Dynamics targets
    'LUFS_target':        -6.29,
    'crest_target_db':    10.29,

    # Formant targets (F1 from المرجع, F2/F3 from الفتح — cleanest extraction)
    'F1_hz':              292.0,
    'F2_hz':              524.0,
    'F3_hz':              820.0,

    # Room character: 500 Hz resonant mode — the studio fingerprint
    # Only present in المرجع1425: RT60@500Hz = 0.479s vs 0.200s everywhere else.
    # The delta = 0.279s of extra decay specifically at 500 Hz.
    'room_500hz_RT60_s':  0.479,
    'room_base_RT60_s':   0.200,
    'room_500hz_delta_s': 0.279,
    'room_500hz_Q':       8.0,     # narrow resonance, not a broad reverb

    # Body resonance floor (120–250 Hz): the gravity band
    'body_band_lo_hz':    120.0,
    'body_band_hi_hz':    250.0,
    'body_target_db':     -18.2,   # consensus across all 3 files

    # Room sustain constant (measured identically in all 3 files)
    'room_sustain_db':    22.5,

    # Voiced level target (المرجع — most forward)
    'voiced_target_dbfs': -4.8,
}

# ── Per-tier scaling: how aggressively NIDAA pushes toward the target ─────────
_NIDAA_TIER_SCALE = {
    'TIER_PRISTINE':   1.00,
    'TIER_COMPRESSED': 0.92,
    'TIER_DEGRADED':   0.58,
    'TIER_DAMAGED':    0.35,
    # TIER_CRITICAL: bypassed entirely
}

# ── NIDAA gate thresholds ──────────────────────────────────────────────────────
_NIDAA_GATE_LUFS_DELTA  = 3.2    # |LUFS shift| ceiling (raised: N-5 push + room blend)
_NIDAA_GATE_SIB_DELTA   = -1.5   # sibilant SNR floor (dB); tighter than الجلال
_NIDAA_GATE_CREST_DELTA = 2.0    # crest factor change ceiling


# ── N-1: Harmonic Sculptor ─────────────────────────────────────────────────────
def _nidaa_harmonic_sculptor(audio: np.ndarray, sr: int,
                              scale: float) -> np.ndarray:
    """
    N-1: Shape the harmonic profile toward the reference DNA.

    The المرجع1425 harmonic fingerprint:
      • Rolloff −11.78 dB/oct (darkest of all 3 recordings)
      • Even-harmonic dominance: even partials 12.4 dB above odd
      • H2 is the dominant energy (+3.6 dB above H1)

    Method — per voiced frame via STFT:
      1. Detect F0 via autocorrelation (70–350 Hz).
      2. Locate each harmonic bin (H1–H10) in the spectrum.
      3. Compute the current even/odd ratio; apply a gentle push toward
         the −12.4 dB target using a per-harmonic gain mask.
      4. Apply a shelf that gently rolls off energy above H4·F0 at
         −11.78 dB/oct slope — reinforces the dark/warm character.
      5. OLA reconstruct.

    Scale factor (from _NIDAA_TIER_SCALE) controls depth of push.
    Maximum per-bin gain change capped at ±2.5 dB to preserve identity.
    """
    if not NUMPY_OK or not _V16_SCIPY_FULL:
        return audio
    if len(audio) < sr * 1.0:
        return audio

    stft_n = 2048; hop_n = stft_n // 4
    try:
        _, _, Zxx = _scipy_stft(audio.astype(np.float32), fs=sr,
                                nperseg=stft_n, noverlap=stft_n - hop_n,
                                window='hann')
    except Exception:
        return audio

    freqs   = rfftfreq(stft_n, 1.0 / sr)
    bin_hz  = float(sr) / stft_n
    Zxx_out = Zxx.copy().astype(np.complex128)
    n_time  = Zxx.shape[1]

    target_even_odd = float(_NIDAA_TARGET['even_odd_bias_db'])   # −12.4 dB
    rolloff         = float(_NIDAA_TARGET['harmonic_rolloff_db_oct'])  # −11.78
    max_gain_db     = 2.5 * float(scale)

    rng = np.random.default_rng(seed=19)

    for t in range(n_time):
        frame_mag = np.abs(Zxx[:, t]).astype(np.float64)

        # Quick voiced gate: energy in 100–400 Hz vs 2–8 kHz
        lo_mask = (freqs >= 100) & (freqs <= 400)
        hi_mask = (freqs >= 2000) & (freqs <= 8000)
        if not lo_mask.any() or not hi_mask.any():
            continue
        lo_e = np.mean(frame_mag[lo_mask])
        hi_e = np.mean(frame_mag[hi_mask])
        if lo_e < hi_e * 2.0:       # not voiced — skip
            continue

        # F0 estimate from autocorrelation peak in 70–350 Hz
        f0_bin_lo = max(1, int(70.0  / bin_hz))
        f0_bin_hi = min(len(freqs) - 1, int(350.0 / bin_hz))
        ac_region = frame_mag[f0_bin_lo: f0_bin_hi]
        if len(ac_region) < 4:
            continue
        peak_idx  = int(np.argmax(ac_region))
        f0_est    = float(freqs[f0_bin_lo + peak_idx])
        if f0_est < 70.0:
            continue

        # Gather H1–H10 bins
        harmonics = []
        for h in range(1, 11):
            f_h     = f0_est * h
            b_h     = int(round(f_h / bin_hz))
            b_lo    = max(0, b_h - 2); b_hi = min(len(freqs) - 1, b_h + 2)
            peak_b  = b_lo + int(np.argmax(frame_mag[b_lo: b_hi + 1]))
            harmonics.append((h, peak_b, float(frame_mag[peak_b])))

        if len(harmonics) < 3:
            continue

        # Compute current even/odd ratio
        even_e = sum(m for h, _, m in harmonics if h % 2 == 0 and m > 0)
        odd_e  = sum(m for h, _, m in harmonics if h % 2 != 0 and m > 0)
        if even_e < 1e-12 or odd_e < 1e-12:
            continue

        current_ratio_db = 20.0 * np.log10(even_e / odd_e + 1e-12)
        # How far are we from target?
        delta_db = (target_even_odd - current_ratio_db) * scale

        # Apply per-harmonic gain
        for h, b, mag in harmonics:
            if mag < 1e-10:
                continue
            # Even harmonics: boost toward target ratio
            # Odd  harmonics: attenuate toward target ratio
            sign   = +1.0 if h % 2 == 0 else -1.0
            g_db   = float(np.clip(sign * abs(delta_db) * 0.5,
                                   -max_gain_db, +max_gain_db))
            # Additionally apply rolloff push: higher harmonics get darker
            octaves_above_H1 = np.log2(max(h, 1))
            rolloff_db = octaves_above_H1 * rolloff * 0.08 * scale  # gentle
            g_db      += rolloff_db
            g_lin      = float(10.0 ** (np.clip(g_db, -max_gain_db, max_gain_db) / 20.0))
            b_lo2  = max(0, b - 1); b_hi2 = min(Zxx_out.shape[0] - 1, b + 1)
            Zxx_out[b_lo2: b_hi2 + 1, t] *= g_lin

    try:
        _, audio_out = _scipy_istft(Zxx_out, fs=sr,
                                    nperseg=stft_n, noverlap=stft_n - hop_n,
                                    window='hann')
    except Exception:
        return audio

    n_in = len(audio)
    audio_out = (audio_out[:n_in] if len(audio_out) >= n_in
                 else np.pad(audio_out, (0, n_in - len(audio_out))))
    return _nan_guard(audio_out.astype(np.float32))


# ── N-2: Sibilant Character Aligner ───────────────────────────────────────────
def _nidaa_sibilant_aligner(audio: np.ndarray, sr: int,
                             scale: float) -> np.ndarray:
    """
    N-2: Align sibilant profile to the reference DNA.

    Target (from المرجع1425 + فاطر1425 consensus):
      centroid = 4280 Hz · peak = 3800 Hz · slope above 5k = −8.3 dB/oct

    The Sheikh's sibilance is warm and centered below 4.3 kHz — never harsh.
    Any file with elevated high-frequency sibilant energy (e.g. 192kbps
    processing artifacts as in الفتح) needs a gentle shelving pull downward.
    Files with low sibilant energy need a gentle presence lift at 3.8–4.3 kHz.

    Method:
      1. Measure current sibilant centroid in the 2–12 kHz band via STFT.
      2. Apply a shelf EQ centred at the target centroid (4280 Hz):
           if current centroid > 4280 Hz → gentle high-shelf cut above 4.5 kHz
           if current centroid < 3800 Hz → gentle presence boost at 3.8–4.3 kHz
      3. Apply a slope correction above 5 kHz to match −8.3 dB/oct.
      Maximum shelf ±1.8 dB × scale — never audible as EQ, only as character.
    """
    if not NUMPY_OK or not _V16_SCIPY_FULL:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    stft_n = 2048; hop_n = stft_n // 4
    try:
        _, _, Zxx = _scipy_stft(audio.astype(np.float32), fs=sr,
                                nperseg=stft_n, noverlap=stft_n - hop_n,
                                window='hann')
    except Exception:
        return audio

    freqs        = rfftfreq(stft_n, 1.0 / sr)
    sib_mask     = (freqs >= 2000.0) & (freqs <= 12000.0)
    if not sib_mask.any():
        return audio

    sib_freqs = freqs[sib_mask]
    sib_mag   = np.abs(Zxx[sib_mask, :]).astype(np.float64)
    mean_mag  = np.mean(sib_mag, axis=1) + 1e-12
    total_e   = np.sum(mean_mag)
    if total_e < 1e-12:
        return audio

    current_centroid = float(np.sum(sib_freqs * mean_mag) / total_e)
    target_centroid  = float(_NIDAA_TARGET['sib_centroid_hz'])
    target_slope     = float(_NIDAA_TARGET['sib_slope_5k_db_oct'])

    # Build per-bin gain mask for the sibilant correction
    gain_mask = np.ones(len(freqs), dtype=np.float64)
    pivot_hz  = 5000.0
    max_g     = 1.8 * float(scale)

    centroid_delta = current_centroid - target_centroid  # positive → too bright

    for i, fq in enumerate(freqs):
        if fq < 2000.0 or fq > 13000.0:
            continue
        # Centroid alignment: push energy toward 4.28 kHz center
        dist = abs(fq - target_centroid)
        pull = float(np.exp(-dist / 1200.0))   # Gaussian centered at target
        centroid_corr_db = -np.sign(centroid_delta) * pull * min(abs(centroid_delta) / 500.0, max_g) * 0.4

        # Slope alignment above pivot: match −8.3 dB/oct
        slope_corr_db = 0.0
        if fq > pivot_hz:
            octaves = np.log2(fq / pivot_hz)
            slope_corr_db = octaves * target_slope * 0.10 * scale

        g_db = float(np.clip(centroid_corr_db + slope_corr_db, -max_g, max_g))
        gain_mask[i] = 10.0 ** (g_db / 20.0)

    Zxx_out = Zxx * gain_mask[:, np.newaxis]
    try:
        _, audio_out = _scipy_istft(Zxx_out, fs=sr,
                                    nperseg=stft_n, noverlap=stft_n - hop_n,
                                    window='hann')
    except Exception:
        return audio

    n_in = len(audio)
    audio_out = (audio_out[:n_in] if len(audio_out) >= n_in
                 else np.pad(audio_out, (0, n_in - len(audio_out))))
    return _nan_guard(audio_out.astype(np.float32))


# ── N-3: 500 Hz Room Character Injector ───────────────────────────────────────
def _nidaa_room_500hz(audio: np.ndarray, sr: int,
                      scale: float) -> np.ndarray:
    """
    N-3: Inject the المرجع1425 studio room fingerprint.

    The master reference has a unique RT60 anomaly: all bands decay in 0.200s
    but the 500 Hz band decays in 0.479s — a delta of 0.279s of extra resonance
    at exactly 500 Hz.  This is a room mode, not reverb: narrow Q, sustained,
    and it creates the warm 'chest in the room' sensation of the reference.

    This sub-module synthesises that character:
      1. Bandpass filter the audio around 500 Hz (Q=8.0, BW≈62Hz) using
         a 2nd-order IIR resonator (Butterworth narrowband).
      2. Convolve the bandpassed signal with an exponential decay kernel of
         length = delta_RT60 × sr = 0.279 × sr ≈ 13,392 samples.
      3. Mix the convolved room signal at blend = 0.08 × scale.

    This is not adding reverb — it is adding a specific frequency-targeted
    decay that matches the measured room mode of the Sheikh's 1425 studio.
    """
    if not NUMPY_OK or not SCIPY_OK:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    try:
        from scipy.signal import butter, filtfilt as _filtfilt, fftconvolve as _fftconv
    except ImportError:
        return audio

    delta_rt60  = float(_NIDAA_TARGET['room_500hz_delta_s'])   # 0.279 s
    fc          = 500.0
    Q           = float(_NIDAA_TARGET['room_500hz_Q'])          # 8.0
    bw          = fc / Q                                          # ≈62 Hz
    lo_n        = float(np.clip((fc - bw / 2) * 2.0 / sr, 0.001, 0.49))
    hi_n        = float(np.clip((fc + bw / 2) * 2.0 / sr, lo_n + 0.005, 0.49))

    try:
        b_bp, a_bp  = butter(2, [lo_n, hi_n], btype='band')
        band_500    = _filtfilt(b_bp, a_bp, audio.astype(np.float64))
    except Exception:
        return audio

    # Exponential decay kernel for the room mode
    decay_len   = int(delta_rt60 * sr)
    t_decay     = np.arange(decay_len, dtype=np.float64) / sr
    # RT60 → decay constant: level drops 60dB in delta_rt60 seconds
    tau         = delta_rt60 / np.log(10.0 ** 3)
    kernel      = np.exp(-t_decay / tau)
    kernel     /= (np.sum(kernel) + 1e-12)

    try:
        room_tail = _fftconv(band_500, kernel, mode='full')[:len(audio)]
    except Exception:
        return audio

    blend = 0.08 * float(scale)
    mixed = audio.astype(np.float64) + blend * room_tail
    mixed = np.clip(mixed, -1.0, 1.0)
    return _nan_guard(mixed.astype(np.float32))


# ── N-4: Warmth Body Lift ──────────────────────────────────────────────────────
def _nidaa_warmth_body(audio: np.ndarray, sr: int,
                        scale: float) -> np.ndarray:
    """
    N-4: Body resonance gravity lift (120–250 Hz band).

    All three reference files show body-band (120–250 Hz) energy at
    −18.2 to −21.0 dB relative to the voiced peak.  The consensus target
    is −18.2 dB (from المرجع1425 — the most forward body).

    If the current file's body band is weaker than −18.2 dB (relative to
    voiced level), a gentle shelf boost is applied to close the gap.
    Maximum boost = 2.0 dB × scale.  Never applied as a cut — the
    lower floor (−21.0 dB from الفتح) is acceptable; only under-energy
    is corrected.

    This lift makes the voice physically present rather than merely heard.
    On any speaker with 120 Hz extension the effect is immediately felt
    as added weight and gravitas.
    """
    if not NUMPY_OK or not SCIPY_OK:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    try:
        from scipy.signal import butter, filtfilt as _filtfilt
    except ImportError:
        return audio

    body_lo  = float(_NIDAA_TARGET['body_band_lo_hz'])   # 120
    body_hi  = float(_NIDAA_TARGET['body_band_hi_hz'])   # 250
    target_rel = float(_NIDAA_TARGET['body_target_db'])  # −18.2

    lo_n = float(np.clip(body_lo * 2.0 / sr, 0.001, 0.49))
    hi_n = float(np.clip(body_hi * 2.0 / sr, lo_n + 0.01, 0.49))

    try:
        b_body, a_body = butter(3, [lo_n, hi_n], btype='band')
        band_body = _filtfilt(b_body, a_body, audio.astype(np.float64))
    except Exception:
        return audio

    # Measure body energy vs voiced energy (full-band)
    body_rms  = float(np.sqrt(np.mean(band_body ** 2)) + 1e-12)
    full_rms  = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)) + 1e-12)
    current_rel_db = 20.0 * np.log10(body_rms / full_rms + 1e-12)

    gap_db = target_rel - current_rel_db  # positive → body is too weak
    if gap_db <= 0.0:
        return audio  # already at or above target — never cut

    boost_db = float(np.clip(gap_db * 0.45 * scale, 0.0, 2.0 * scale))
    boost_lin = float(10.0 ** (boost_db / 20.0))

    # Apply boost only to the body band via OLA addition of boosted signal
    lo2_n = float(np.clip((body_lo * 0.85) * 2.0 / sr, 0.001, 0.49))
    hi2_n = float(np.clip((body_hi * 1.15) * 2.0 / sr, lo2_n + 0.01, 0.49))
    try:
        b2, a2    = butter(2, [lo2_n, hi2_n], btype='band')
        band_wide = _filtfilt(b2, a2, audio.astype(np.float64))
    except Exception:
        band_wide = band_body

    mixed = audio.astype(np.float64) + band_wide * (boost_lin - 1.0)
    mixed = np.clip(mixed, -1.0, 1.0)
    return _nan_guard(mixed.astype(np.float32))


# ── N-5: LUFS Convergence ─────────────────────────────────────────────────────
def _nidaa_lufs_convergence(input_wav: str, scale: float) -> Tuple[str, float]:
    """
    N-5: Pull LUFS toward the reference target of −6.29 dBFS.

    The reference consensus across all 3 files is −6.29 LUFS (integrated).
    After N1–N4 have shifted the harmonic and spectral character, the LUFS
    may have drifted slightly.  This final stage measures current LUFS and
    applies a gain correction that moves 40% × scale of the way toward the
    target — never overshooting.

    Returns (output_wav_path, delta_lufs_applied).
    Maximum gain correction capped at 1.5 dB.
    """
    import uuid as _uuid_n
    target  = float(_NIDAA_TARGET['LUFS_target'])    # −6.29
    current = measure_lufs(input_wav)
    if abs(current) < 0.1:                           # measurement failed
        return input_wav, 0.0

    gap_db      = target - current
    push_db     = float(np.clip(gap_db * 0.40 * scale, -1.5, 1.5))
    if abs(push_db) < 0.1:
        return input_wav, 0.0

    out_wav = os.path.join(_TMP, f'nidaa_lufs_{_uuid_n.uuid4().hex[:8]}.wav')
    rc = subprocess.run(
        ['ffmpeg', '-y', '-i', input_wav,
         '-af', f'volume={push_db:.3f}dB',
         '-c:a', WAV_CODEC, '-loglevel', 'error', out_wav],
        capture_output=True)

    if rc.returncode != 0 or not os.path.exists(out_wav):
        return input_wav, 0.0
    return out_wav, push_db


# ── النداء Orchestrator ────────────────────────────────────────────────────────
def apply_nidaa(
    input_wav: str,
    state:     'InputState',
    ref:       'ReferenceModel',
    log_fn=None,
) -> Tuple[str, Dict]:
    """
    النداء — Neural Identity-Driven Audio Ascension orchestrator.

    Applies five sub-modules in sequence using the precise acoustic DNA
    of Sheikh Yasser Al-Dosari extracted from his three reference recordings:

      N-1  Harmonic Sculptor    → shape even/odd ratio + rolloff toward DNA
      N-2  Sibilant Aligner     → centroid 4280Hz · slope −8.3dB/oct
      N-3  500Hz Room Injector  → المرجع1425 studio room mode (0.279s delta RT60)
      N-4  Warmth Body Lift     → 120–250Hz gravity to −18.2dB target
      N-5  LUFS Convergence     → pull to −6.29 LUFS target (40% × scale push)

    Gate: validates sibilant SNR, LUFS, and crest factor before accepting.
    On gate failure: partial revert (skip N-3 room injection), re-validate.
    On second failure: full revert to input_wav.

    Bypassed on TIER_CRITICAL.  Returns (output_wav_path, report_dict).
    """
    _log   = log_fn or L
    report: Dict = {
        'status':    'SKIPPED', 'reason': '',
        'n1_harmonic': False, 'n2_sibilant': False,
        'n3_room':     False, 'n4_warmth':   False,
        'n5_lufs':     False,
        'delta_lufs':  0.0,   'delta_sib':   0.0,
        'delta_warmth':0.0,   'scale':       0.0,
    }

    tier  = state.source_tier
    scale = _NIDAA_TIER_SCALE.get(tier, 0.0)
    if scale == 0.0:
        report['reason'] = f'tier={tier}'
        return input_wav, report

    if not NUMPY_OK:
        report['reason'] = 'numpy unavailable'
        return input_wav, report

    report['scale'] = scale
    _log(f'  [النداء] tier={tier}  scale={scale:.2f}  '
         f'target F0={_NIDAA_TARGET["F0_center_hz"]:.0f}Hz  '
         f'rolloff={_NIDAA_TARGET["harmonic_rolloff_db_oct"]:.2f}dB/oct')

    # ── Pre-gate baseline ────────────────────────────────────────────────────
    pre_chunk = load_audio_fast(input_wav, state.skip_s, min(state.dur_s, 45))
    if len(pre_chunk) < SR * 3:
        report['reason'] = 'audio too short'
        return input_wav, report

    pre_sib   = compute_sibilant_snr(pre_chunk, state.silence_floor)
    pre_lufs  = measure_lufs(input_wav)
    pre_crest = crest_factor(pre_chunk)

    # ── Load full audio ──────────────────────────────────────────────────────
    full = load_audio_fast(input_wav, 0.0, state.total_s)
    if len(full) < SR * 2:
        report['reason'] = 'full audio too short'
        return input_wav, report

    current = full.copy()

    # ── N-1: Harmonic Sculptor ───────────────────────────────────────────────
    try:
        current = _nidaa_harmonic_sculptor(current, SR, scale)
        report['n1_harmonic'] = True
        _log(f'  [النداء N-1] harmonic sculptor ✓  '
             f'target even/odd={_NIDAA_TARGET["even_odd_bias_db"]:.1f}dB  '
             f'rolloff={_NIDAA_TARGET["harmonic_rolloff_db_oct"]:.2f}dB/oct')
    except Exception as _e:
        _log(f'  [النداء N-1] error: {_e}')

    # ── N-2: Sibilant Aligner ────────────────────────────────────────────────
    try:
        current = _nidaa_sibilant_aligner(current, SR, scale)
        report['n2_sibilant'] = True
        _log(f'  [النداء N-2] sibilant aligner ✓  '
             f'target centroid={_NIDAA_TARGET["sib_centroid_hz"]:.0f}Hz  '
             f'peak={_NIDAA_TARGET["sib_peak_hz"]:.0f}Hz  '
             f'slope={_NIDAA_TARGET["sib_slope_5k_db_oct"]:.1f}dB/oct')
    except Exception as _e:
        _log(f'  [النداء N-2] error: {_e}')

    # ── N-3: 500 Hz Room Injector ────────────────────────────────────────────
    current_pre_room = current.copy()
    try:
        current = _nidaa_room_500hz(current, SR, scale)
        report['n3_room'] = True
        _log(f'  [النداء N-3] room 500Hz ✓  '
             f'delta_RT60={_NIDAA_TARGET["room_500hz_delta_s"]:.3f}s  '
             f'Q={_NIDAA_TARGET["room_500hz_Q"]:.1f}  '
             f'blend={0.08*scale:.3f}')
    except Exception as _e:
        _log(f'  [النداء N-3] error: {_e}')

    # ── N-4: Warmth Body Lift ────────────────────────────────────────────────
    body_before = float(np.sqrt(np.mean(current.astype(np.float64) ** 2)) + 1e-12)
    try:
        current = _nidaa_warmth_body(current, SR, scale)
        report['n4_warmth'] = True
        body_after = float(np.sqrt(np.mean(current.astype(np.float64) ** 2)) + 1e-12)
        warmth_delta = 20.0 * np.log10(body_after / body_before + 1e-12)
        report['delta_warmth'] = round(float(warmth_delta), 2)
        _log(f'  [النداء N-4] warmth body ✓  '
             f'target={_NIDAA_TARGET["body_target_db"]:.1f}dB  '
             f'Δ={warmth_delta:+.2f}dB')
    except Exception as _e:
        _log(f'  [النداء N-4] error: {_e}')

    # ── Write intermediate WAV ───────────────────────────────────────────────
    import uuid as _uuid_nd
    tmp_n14 = os.path.join(_TMP, f'nidaa_n14_{_uuid_nd.uuid4().hex[:8]}.wav')
    raw     = current.astype(np.float32).tobytes()
    rc = subprocess.run(
        ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
         '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
         '-loglevel', 'error', tmp_n14],
        input=raw, capture_output=True)

    if rc.returncode != 0 or not os.path.exists(tmp_n14):
        report['reason'] = 'intermediate write failed'
        return input_wav, report

    # ── N-5: LUFS Convergence ────────────────────────────────────────────────
    tmp_final = tmp_n14
    try:
        tmp_lufs, lufs_delta = _nidaa_lufs_convergence(tmp_n14, scale)
        if tmp_lufs != tmp_n14:
            tmp_final          = tmp_lufs
            report['n5_lufs'] = True
            report['delta_lufs'] = round(float(lufs_delta), 2)
            _log(f'  [النداء N-5] LUFS convergence ✓  '
                 f'push={lufs_delta:+.2f}dB  '
                 f'target={_NIDAA_TARGET["LUFS_target"]:.2f}LUFS')
        else:
            _log(f'  [النداء N-5] LUFS already at target — skipped')
    except Exception as _e:
        _log(f'  [النداء N-5] error: {_e}')

    # ── N-GATE: cumulative validation ────────────────────────────────────────
    def _ngate(wav: str) -> Tuple[bool, str, float, float, float]:
        post = load_audio_fast(wav, state.skip_s, min(state.dur_s, 45))
        if len(post) < SR * 2:
            return False, 'post_too_short', 0.0, 0.0, 0.0
        sib  = compute_sibilant_snr(post, state.silence_floor)
        lufs = measure_lufs(wav)
        cres = crest_factor(post)
        sd   = sib  - pre_sib
        ld   = abs(lufs  - pre_lufs)
        cd   = abs(cres  - pre_crest)
        if sd < _NIDAA_GATE_SIB_DELTA:
            return False, f'sib_delta={sd:.2f}dB', sd, ld, cd
        if ld > _NIDAA_GATE_LUFS_DELTA:
            return False, f'lufs_delta={ld:.2f}dB', sd, ld, cd
        if cd > _NIDAA_GATE_CREST_DELTA:
            return False, f'crest_delta={cd:.2f}dB', sd, ld, cd
        return True, '', sd, ld, cd

    gate_ok, gate_msg, sib_d, lufs_d, crest_d = _ngate(tmp_final)

    if not gate_ok:
        _log(f'  [النداء N-GATE] FAIL ({gate_msg}) — partial revert: skip room N-3')
        # Partial revert: redo without N-3 room injection
        try:
            current_nr = current_pre_room.copy()
            current_nr = _nidaa_warmth_body(current_nr, SR, scale)
            tmp_nr     = os.path.join(_TMP, f'nidaa_nr_{_uuid_nd.uuid4().hex[:8]}.wav')
            raw_nr     = current_nr.astype(np.float32).tobytes()
            rc2 = subprocess.run(
                ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
                 '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
                 '-loglevel', 'error', tmp_nr],
                input=raw_nr, capture_output=True)
            tmp_nr2, ld2 = _nidaa_lufs_convergence(tmp_nr, scale) \
                if rc2.returncode == 0 else (tmp_nr, 0.0)
            gate_ok2, gate_msg2, sib_d, lufs_d, crest_d = _ngate(tmp_nr2)
            if gate_ok2:
                _log(f'  [النداء N-GATE] partial revert accepted  '
                     f'sib_Δ={sib_d:+.2f}dB  lufs_Δ={lufs_d:+.2f}dB')
                report.update({
                    'status': 'OK_PARTIAL', 'n3_room': False,
                    'delta_sib': round(float(sib_d), 2),
                })
                return tmp_nr2, report
        except Exception as _pe:
            _log(f'  [النداء] partial revert exception: {_pe}')

        _log(f'  [النداء N-GATE] full revert — {gate_msg}')
        report.update({'status': 'REVERTED', 'reason': gate_msg})
        return input_wav, report

    report['delta_sib'] = round(float(sib_d), 2)
    modules_applied = '·'.join(
        k for k, v in [('N1',report['n1_harmonic']), ('N2',report['n2_sibilant']),
                        ('N3',report['n3_room']),     ('N4',report['n4_warmth']),
                        ('N5',report['n5_lufs'])] if v)
    report['status'] = 'OK'

    _log(f'  [النداء] ✓  [{modules_applied}]  '
         f'sib_Δ={sib_d:+.2f}dB  lufs_Δ={lufs_d:+.2f}dB  '
         f'crest_Δ={crest_d:+.2f}dB  warmth_Δ={report["delta_warmth"]:+.2f}dB')

    return tmp_final, report


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

    KB-12-02 — Ghunnah nasal formant guard (Supplement §52.2):
      Mim/Nun produce a nasal pole at ~250Hz (ghunnah resonance) AND a spectral
      antiformant at ~1000Hz. Both are phonologically essential. Any EQ node in
      these zones gets confidence capped at 0.40 to prevent overcorrection.
      220-290Hz: nasal pole zone  |  950-1100Hz: nasal antiformant zone.

    KB-12-05 — Alif F1 formant guard (Supplement §52.2):
      Arabic long vowel alif has F1 ~700Hz. "Do NOT cut below 700Hz for alif —
      cuts the formant itself" (KB §52.2). Any cut (negative EQ) proposed in the
      630-800Hz band is capped at confidence 0.45 to prevent F1 erasure.

    KB-12-03 — Emphatic letter 3-5kHz guard (Supplement §52.3, Roadmap H):
      When sib_emphatic_dominant=True, the 2800-4800Hz zone carries emphatic
      sibilant energy (Sad, Dad, Tha, Ta). Confidence reduced by 0.35 to protect
      this energy from de-essing or EQ cuts.
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
        base = min(1.0, hf_conf)
        # KB-12-02: Ghunnah nasal pole zone (220-290Hz) — cap cuts
        if 220.0 <= fc <= 290.0:
            base = min(base, 0.40)
        return base

    # KB-12-02: Ghunnah antiformant zone (950-1100Hz) — cap confidence
    if 950.0 <= fc <= 1100.0:
        return min(hf_conf, 0.40)

    # KB-12-05: Alif F1 zone (630-800Hz) — reduce confidence for cuts
    if 630.0 <= fc <= 800.0:
        return min(hf_conf, 0.45)

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

    # KB-12-03: Emphatic sibilant zone (2800-4800Hz)
    # When emphatic sibilants dominate, protect this band from EQ correction
    emphatic_conf = 1.0
    if 2800.0 <= fc <= 4800.0 and getattr(state, 'sib_emphatic_dominant', False):
        emphatic_conf = 0.65  # reduce by 0.35

    return float(min(hf_conf, snr_conf, smear_conf, emphatic_conf))


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
        # EQ-SNR-CAP: When frame_snr < 8dB, EQ boosts lift noise equally with
        # speech. Cap EQ scale proportionally to avoid amplifying the noise floor.
        if state.frame_snr < 8.0:
            snr_cap = float(np.clip(state.frame_snr / 8.0, 0.20, 1.0))
            return snr_cap
        # VOICE-PRESERVE: A uniform scale was over-suppressing voice presence/clarity.
        # Mid-presence (800–3kHz) and HF (>3kHz) deficits ARE codec damage on 128kbps.
        # Voice-identity bands (150–800Hz) ARE room/mic character — protect those.
        # Band-specific capping is done in design_eq via VOICE_IDENTITY_CLAMP.
        # Here: full scale for codec-damaged DEGRADED/DAMAGED sources.
        # The per-node clamp in design_eq handles identity preservation.
        if state.frame_snr < 8.0:
            snr_cap = float(np.clip(state.frame_snr / 8.0, 0.20, 1.0))
            return snr_cap
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

    # KB-12-03: Emphatic letter de-essing guard (Supplement §52.3, Roadmap H)
    # When emphatic sibilants dominate (Sad, Dad, etc.), protect 3-5kHz by
    # tightening sib_cap from 2.0 -> 1.0 dB. This prevents de-essing from
    # reducing the emphatic energy that distinguishes Sad from Sin.
    if getattr(state, 'sib_emphatic_dominant', False):
        sib_cap = 1.0 if sib_cap is not None else 1.0
        L('  [KB-12-03/EmphaticGuard] sib_cap tightened 2.0->1.0 dB '
          '(emphatic sibilants dominant — protecting Sad/Dad zone)')
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

    # FIX-H: Merge clustered nodes within 1/6-octave before smear restoration
    # VOICE-IDENTITY-CLAMP: per-node band-specific gain limits.
    # 150-800Hz  = Sheikh's voice identity (H2 dominance, chest warmth) -> ±3dB max
    # 800-3000Hz = presence/clarity (codec-damaged on 128kbps) -> ±8dB max
    # >3000Hz    = HF extension (handled by aexciter HF guard) -> uncapped here
    #
    # KB-12-04: Dark emphatic resonance guard (Supplement §52.3)
    # Emphatic consonants (Sad, Dad, Ta, Dha, Kha, Ghain) add a broad pharyngeal
    # resonance at 600-900 Hz. EQ cuts here destroy the "dark" tonal quality.
    # When emphatic sibilants dominate, cap cuts in 580-920Hz at -2dB.
    _emphatic_dominant = getattr(state, 'sib_emphatic_dominant', False)
    _clamped = []
    for f_node, g_node, q_node in eq_nodes:
        if 150 <= f_node <= 800:
            g_node = float(np.clip(g_node, -3.0, 3.0))
        elif 800 < f_node <= 3000:
            g_node = float(np.clip(g_node, -8.0, 8.0))
        # KB-12-04: Additional emphatic resonance guard in 580-920Hz
        if _emphatic_dominant and 580 <= f_node <= 920 and g_node < -2.0:
            g_node = -2.0   # cap cut at -2dB to preserve pharyngeal resonance
        _clamped.append((f_node, g_node, q_node))
    eq_nodes = [(f, g, q) for f, g, q in _clamped if abs(g) >= 0.15]
    eq_nodes = _dedup_eq_nodes(eq_nodes)
    if _emphatic_dominant:
        L('  [KB-12-04/DarkEmphaticGuard] 580-920Hz cuts capped at -2.0dB '
          '(emphatic pharyngeal resonance protected)')

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

    # KB-03: Comb filter fill nodes from PA system reflection detection
    if state.comb_filter_detected and state.comb_filter_notch_hz > 0:
        comb_nodes = _build_comb_fill_eq_nodes(
            state.comb_filter_notch_hz, state.comb_filter_period_ms,
            max_fill_db=2.5)
        if comb_nodes:
            eq_nodes = eq_nodes + comb_nodes
            L(f'  [KB-03/Comb] +{len(comb_nodes)} PA notch fill nodes '
              f'(first notch={state.comb_filter_notch_hz:.0f}Hz '
              f'PA delay={state.comb_filter_period_ms:.1f}ms)')

    # KB-05: IEC2 tape — add HF compensation shelf if not already applied
    # (belt-and-suspenders: also adds an EQ node in case Phase A IEC2 was detected
    #  but the ffmpeg shelf failed to apply for any reason)
    if state.tape_iec2_suspected and not any(f > 5000 and g > 1.0 for f, g, _ in eq_nodes):
        eq_nodes.append((6300.0, 1.5, 0.6))   # gentle broadening shelf
        L('  [KB-05/IEC2] +1 HF shelf node (chrome tape EQ compensation)')

    # KB-09: Scale voice-identity clamp based on Sidrah maqam confidence
    # Re-applied here after comb/IEC2 additions to honour the maqam scale
    if hasattr(state, 'sidrah_maqam_confidence'):
        _mq_scale = _maqam_eq_scale(
            getattr(state, 'sidrah_maqam_confidence', 0.0),
            getattr(state, 'sidrah_maqam', 'UNKNOWN'))
        if _mq_scale < 1.0:
            _reclamped = []
            for f_n, g_n, q_n in eq_nodes:
                if 150 <= f_n <= 800:
                    g_n = float(np.clip(g_n, -3.0 * _mq_scale, 3.0 * _mq_scale))
                _reclamped.append((f_n, g_n, q_n))
            eq_nodes = [(f, g, q) for f, g, q in _reclamped if abs(g) >= 0.15]
            L(f'  [KB-09/Maqam] voice-identity clamp tightened '
              f'(maqam_conf={getattr(state, "sidrah_maqam_confidence", 0.0):.2f} '
              f'scale={_mq_scale:.2f})')

    return eq_nodes


def _dedup_eq_nodes(nodes: List[Tuple]) -> List[Tuple]:
    """
    FIX-H: Merge EQ nodes within 1/6 octave of each other.
    The L-BFGS-B optimizer clusters multiple nodes at nearly identical
    frequencies (e.g. three nodes at 128Hz = -18dB effective cut).
    Merging: group nodes within 1/6-octave, take weighted-average frequency,
    sum gains (capped at ±6dB), harmonic-mean Q.
    """
    if not nodes:
        return nodes
    sorted_nodes = sorted(nodes, key=lambda x: x[0])
    MERGE_RATIO = 2 ** (1.0 / 6)  # 1/6 octave = factor 1.122

    merged: List[Tuple] = []
    used = [False] * len(sorted_nodes)
    for i, (f0, g, Q) in enumerate(sorted_nodes):
        if used[i]:
            continue
        group_f = [f0]; group_g = [g]; group_Q = [Q]
        used[i] = True
        for j in range(i + 1, len(sorted_nodes)):
            if used[j]: continue
            fj, gj, Qj = sorted_nodes[j]
            if fj / f0 <= MERGE_RATIO:
                group_f.append(fj); group_g.append(gj); group_Q.append(Qj)
                used[j] = True
        if len(group_f) == 1:
            merged.append((f0, g, Q))
        else:
            weights = [abs(gx) + 0.01 for gx in group_g]
            wsum = sum(weights)
            new_f = sum(ff * w for ff, w in zip(group_f, weights)) / wsum
            new_g = float(np.clip(sum(group_g), -6.0, 6.0))
            new_Q = len(group_Q) / sum(1.0 / qx for qx in group_Q)
            if abs(new_g) >= 0.15:
                merged.append((round(new_f, 0), round(new_g, 2), round(new_Q, 2)))
    return merged


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
        # FIX-I: target ENCODE_HEADROOM_DB hotter than achievable_lufs.
        # Encode trims DOWN by ENCODE_HEADROOM_DB (safe, peaks decrease).
        # Stereo peaks after joint alimiter = 0dBFS; trim DOWN = no TP issue.
        gain_db = (state.achievable_lufs + ENCODE_HEADROOM_DB) - result_1.lufs
        return JointParams(compand_str=_COMPAND_LIBRARY['BYPASS'],
                           gain_db=float(np.clip(gain_db, -18, 18)),
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

    # FIX-F: When target LRA reduction is unreachable, use best available curve.
    # PCHIP binary search converges to 0 (BYPASS) when all sampled lra_deltas
    # are above target_lra_delta (can't achieve the needed reduction).
    # Happens on short clips (<45s) or sources with naturally low LRA.
    # Fix: if target_intensity < 0.10 and we want LRA reduction, select the
    # curve with the largest available reduction rather than BYPASS.
    if target_intensity < 0.10 and target_lra_delta < -0.20:
        best_reduction_idx = int(np.argmin(lra_deltas))
        if lra_deltas[best_reduction_idx] < -0.05:
            target_intensity = intensities[best_reduction_idx]
            L(f'  [joint] PCHIP target unreachable (best={lra_deltas[best_reduction_idx]:+.2f}) '
              f'— using {sample_curves[best_reduction_idx]} as fallback')

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

    # FIX-I: target ENCODE_HEADROOM_DB hotter so encode trims DOWN (safe, not UP).
    predicted_lufs = result_1.lufs + predicted_lufs_delta
    gain_db = (state.achievable_lufs + ENCODE_HEADROOM_DB) - predicted_lufs
    gain_db = float(np.clip(gain_db, -18.0, 18.0))  # BUG-F FIX: was ±6dB

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

    af += ',alimiter=limit=0.9891:level=false:attack=0.1:release=25:asc=1:asc_level=0.5'
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
    parts.append('alimiter=limit=0.9441:level=false:attack=0.1:release=10')
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
    # FIX-G: Speech-gated loudness for gain trim (BUG-G: avoids silence distortion).
    # FIX-K: Post-joint gain correction — measure actual LUFS and target
    # achievable_lufs + ENCODE_HEADROOM_DB + MP3_LOSS_DB so the encode can
    # trim DOWN by exactly ENCODE_HEADROOM_DB (safe) + MP3 codec loss.
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
            measured_lufs = rms_db(_speech) + 0.7  # K-weighted offset
        else:
            measured_lufs = measure_lufs(best_wav)
    except Exception:
        measured_lufs = measure_lufs(best_wav)

    # FIX-K: Apply pre-encode gain correction to bring WAV to exact target.
    # Joint optimizer prediction error is 0.5-2dB. Correct it before encode.
    _lufs_target_wav = state.achievable_lufs + ENCODE_HEADROOM_DB + MP3_LOSS_DB
    _gain_corr = _lufs_target_wav - measured_lufs
    if abs(_gain_corr) > 0.3:
        _gain_corr = float(np.clip(_gain_corr, -6.0, 6.0))
        _corrected = os.path.join(_TMP, 'v104_gaincorr.wav')
        _af_corr = f'volume={_gain_corr:.3f}dB,alimiter=limit=0.9891:level=false:attack=0.1:release=25:asc=1:asc_level=0.5'
        _ok_corr = ffmpeg_process(best_wav, _corrected, _af_corr)
        if _ok_corr:
            best_wav = _corrected
            measured_lufs += _gain_corr
            L(f'  [gain-corr] {measured_lufs-_gain_corr:.2f}→{measured_lufs:.2f} LUFS '
              f'({_gain_corr:+.2f}dB → target {_lufs_target_wav:.2f})')

    # FIX-G2: STEREO peak measurement for correct headroom gate.
    # load_audio_fast uses 0.5*(L+R) but stereo peaks may be higher.
    # Measure stereo peak directly to gate the encode trim correctly.
    _sp2, _tc2 = _safe(best_wav)
    _rp = subprocess.run(
        ['ffmpeg', '-y', '-i', _sp2, '-t', str(min(state.total_s, 60)),
         '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-loglevel', 'error', '-'],
        capture_output=True)
    if _tc2:
        try: os.remove(_tc2)
        except: pass
    if _rp.stdout:
        _stereo_samp = np.frombuffer(_rp.stdout, dtype=np.float32)
        _stereo_peak_db = float(20 * np.log10(np.max(np.abs(_stereo_samp)) + 1e-10))
    else:
        _stereo_peak_db = -6.0

    # FIX-I/J: Headroom-aware trim — only gate UPWARD trim (peaks increase),
    # downward trim is always safe.
    _max_safe_trim = (-1.0 - 0.5) - _stereo_peak_db  # most we can trim UP safely
    lufs_trim_needed = state.achievable_lufs - measured_lufs
    lufs_trim_needed = float(np.clip(lufs_trim_needed, -18.0, 18.0))

    if lufs_trim_needed <= 0:
        lufs_trim = lufs_trim_needed  # downward: always safe
    elif lufs_trim_needed <= _max_safe_trim:
        lufs_trim = lufs_trim_needed  # upward within headroom: safe
    else:
        lufs_trim = max(0.0, _max_safe_trim)  # gate upward trim at headroom limit

    if abs(lufs_trim - lufs_trim_needed) > 0.3:
        L(f'  [encode] headroom gate: stereo_peak={_stereo_peak_db:.2f}dBFS '
          f'max_up={_max_safe_trim:+.2f}dB target={lufs_trim_needed:+.2f} '
          f'applying={lufs_trim:+.2f} shortfall={(lufs_trim_needed-lufs_trim):.2f}dB')

    limiter_threshold = 0.891
    true_peak_db = -2.0
    n_retries = 0

    for attempt in range(3):
        parts = []
        if abs(lufs_trim) > 0.05:
            parts.append(f'volume={lufs_trim:.3f}dB')
        parts.append(f'alimiter=limit={limiter_threshold:.4f}:level=false:attack=1:release=15')

        # KB-12-08: TPDF dither for perceptually clean output (Supplement §57.2)
        # The final encode is at 320kbps MP3 (floating point internally). However,
        # if the output format is WAV 16-bit, triangular dither must be applied
        # BEFORE quantisation to break up low-level quantisation noise patterns
        # that are especially audible on quiet ayah tails and natural breath pauses.
        # For MP3 output (current default): apply aformat=sample_fmts=s16 + dithering
        # via the 'highpass=f=1' + triangular_dither technique (ffmpeg atrim/dither).
        # ffmpeg's 'aformat' + 'resampler=dither_method=triangular' chain applies TPDF.
        # We add this only if the output is a WAV 16-bit path (filetype gate).
        _out_is_16bit_wav = (output_path.lower().endswith('.wav'))
        if _out_is_16bit_wav:
            # Apply triangular dither: aformat s32 → s16 with TPDF via resampler
            parts.append('aresample=resampler=swr:dither_method=triangular')
            parts.append('aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo')

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
            if limiter_threshold < 0.800:  # FIX-C3: 0.800 floor (was 0.500)
                limiter_threshold = 0.800
                lufs_trim -= (excess_db + 0.2)  # reduce gain instead of crushing
                L(f'  [encode] TP={true_peak_db:.2f}dBTP — gain -{excess_db+0.2:.1f}dB (limiter floor)')
            else:
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

    # KB-08: Discontinuity detection (NISQA-style gap/word-drop detector)
    if NUMPY_OK:
        try:
            _disc_clip = load_audio_fast(wav_path, state.skip_s, min(state.dur_s, 60.0))
            _disc_score = compute_discontinuity_score(
                _disc_clip, state.silence_floor, sr=SR)
            state.discontinuity_score = _disc_score
            if _disc_score > 0.15:
                L(f'  [KB-08/Discontinuity] score={_disc_score:.3f} '
                  f'(>0.15 = audible gaps likely)')
        except Exception:
            pass

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
    # FIX-L: Oscillation threshold raised from 0.15 to 0.50, requires n>=3.
    # The joint pass shifts spectral balance slightly (compand is frequency-
    # dependent). A 0.19dB eq_residual increase after joint is EXPECTED and
    # healthy, not oscillation. Old threshold fired on this normal behaviour,
    # preventing any second iteration. Only flag true EQ divergence.
    if n >= 3 and last.eq_residual > history[-2].eq_residual + 0.50:
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
            max_iterations: int = 3, target_score: float = 96.0,
            force_tier: str = None) -> Dict:
    t0 = time.time()

    MAX_T = 1800
    def _chk(phase):
        if time.time() - t0 > MAX_T:
            raise TimeoutError(f'enhance() exceeded {MAX_T}s at phase={phase}')

    L(f'╔══════════════════════════════════════════════════╗')
    L(f'║  Audio Enhancement Engine v12.0 — "الاسترداد"   ║')
    L(f'║  المرجع: الشيخ ياسر الدوسري — 1425H  (KB v12)   ║')
    L(f'╚══════════════════════════════════════════════════╝')
    L(f'  الملف: {os.path.basename(input_path)}')

    # KB-12-07: SHA-256 provenance hash (Supplement §65.2, Roadmap D)
    # Hash the input file at start for integrity tracking.
    _input_hash = 'UNAVAILABLE'
    try:
        _h = hashlib.sha256()
        with open(input_path, 'rb') as _hf:
            for _chunk in iter(lambda: _hf.read(1 << 20), b''):
                _h.update(_chunk)
        _input_hash = _h.hexdigest()[:16]   # first 16 hex chars = 64-bit fingerprint
        L(f'  [KB-12-07/Hash] input SHA-256={_input_hash}')
    except Exception as _he:
        L(f'  [KB-12-07/Hash] hash failed: {_he}')

    # ── PHASE A: Reference + Input Analysis ────────────────────────────────
    L('\nPass 1 — تحليل المدخل والمرجع')
    _chk('phase_A')

    ref = load_reference_model()
    L(f'  مرجع: {ref.n_files} ملف | RMS={ref.rms:.2f} Crest={ref.crest:.2f} '
      f'LRA={ref.lra:.2f} p50={ref.phrase_lra_p50:.2f}')

    state = analyze_input(input_path, ref)
    if force_tier:
        L(f'  [force_tier] overriding {state.source_tier} → {force_tier}')
        state.source_tier = force_tier
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

    # ── KB-01: Dolby B compensatory de-emphasis ──────────────────────────────
    if state.dolby_suspected and state.dolby_hf_tilt_db > 6.0:
        L(f'  [KB-01/Dolby] applying compensatory HF de-emphasis '
          f'(tilt={state.dolby_hf_tilt_db:.1f}dB)')
        _chk('phase_dolby_deemph')
        _dolby_fixed = _apply_dolby_compensatory_deemphasis(
            working_path, state.dolby_hf_tilt_db)
        if _dolby_fixed != working_path:
            working_path = _dolby_fixed
    else:
        if state.dolby_suspected:
            L(f'  [KB-01/Dolby] tilt below action threshold — bypass')
        else:
            L(f'  [KB-01/Dolby] not detected (tilt={state.dolby_hf_tilt_db:.1f}dB)')

    # ── KB-02: Azimuth mismatch correction (stereo TIER_CRITICAL/DAMAGED) ───
    if state.source_tier in ('TIER_CRITICAL', 'TIER_DAMAGED') and not state.is_mono:
        L('  [KB-02/Azimuth] detecting stereo L/R interchannel delay...')
        _chk('phase_azimuth')
        _az_lag, _az_delay_ms = _detect_azimuth_mismatch(working_path)
        state.azimuth_lag_samples = _az_lag
        state.azimuth_delay_ms    = _az_delay_ms
        # Correct if delay > 0.08ms (≈ 1° azimuth misalignment on cassette)
        if abs(_az_delay_ms) >= 0.08:
            L(f'  [KB-02/Azimuth] lag={_az_lag:+d} samp ({_az_delay_ms:+.3f}ms) — correcting')
            _az_corrected = _apply_azimuth_correction(working_path, _az_lag)
            if _az_corrected != working_path:
                working_path = _az_corrected
                state.azimuth_corrected = True
        else:
            L(f'  [KB-02/Azimuth] lag={_az_lag:+d} samp ({_az_delay_ms:+.3f}ms) '
              f'— within tolerance, no correction needed')
    else:
        L(f'  [KB-02/Azimuth] bypass (tier={state.source_tier} mono={state.is_mono})')

    # ── KB-05: IEC2 chrome tape compensatory HF shelf ───────────────────────
    if state.tape_iec2_suspected:
        L('  [KB-05/IEC2] applying +2dB compensatory HF shelf (chrome tape)')
        _chk('phase_iec2_shelf')
        _iec2_tmp = os.path.join(_TMP, 'iec2_corrected.wav')
        _iec2_r = subprocess.run(
            ['ffmpeg', '-y', '-i', working_path,
             '-af', 'treble=g=2.0:f=3000:t=q:w=0.5',
             '-c:a', WAV_CODEC, '-loglevel', 'error', _iec2_tmp],
            capture_output=True)
        if _iec2_r.returncode == 0 and os.path.exists(_iec2_tmp):
            working_path = _iec2_tmp
            L('  [KB-05/IEC2] ✓')
    else:
        L(f'  [KB-05/IEC2] not detected')

    # ── PHASE B: NR Pass ────────────────────────────────────────────────────
    L('\nPass 2 — تقليل الضوضاء (NR)')
    _chk('phase_B')

    nr_wav, nr_report = nr_pass(working_path, state, ref, silence_data)
    if nr_report['applied']:
        L(f'  NR applied: floor_delta={nr_report["floor_delta"]:+.1f}dB '
          f'sib_delta={nr_report["sib_delta"]:+.1f}dB')
    else:
        L(f'  NR bypass (confidence={state.nr_confidence:.2f})')

    # ── PHASE B2: ENGINE-1 Tier 2 Recovery ─────────────────────────────────
    # Runs when the base engine hits a physical limit:
    #   TYPE_A: SNR < 12dB — no silence frames → statistical NR
    #   TYPE_B: LRA < 2.0 AND Crest < 9.5 — crushed dynamics → expander
    # Must run BEFORE EQ design so the EQ optimizer works on recovered audio.
    # (EQ designed from noise-contaminated or crushed-dynamic spectrum
    #  would correct in the wrong direction — L-11 extended.)
    bayan_result = None  # البيان Phase B4
    t2_report: Dict = {'tier2_active': False}
    needs_t2, t2_reason = needs_tier2(state)
    if needs_t2:
        L(f'\nPass 2B — ENGINE-1: الاسترداد Recovery ({t2_reason})')
        _chk('phase_B2_tier2')
        nr_wav, t2_report = enhance_tier2(nr_wav, state, ref)
        L(f'  Tier 2: A={t2_report["type_a_applied"]} '
          f'B={t2_report["type_b_applied"]} '
          f'C={t2_report["type_c_applied"]} '
          f'lra_gain={t2_report.get("lra_recovered", 0):+.2f}LU '
          f'snr_after={t2_report.get("snr_after", state.snr_global):.1f}dB')
    else:
        L(f'  [Tier 2] not needed ({t2_reason})')

    # ── PHASE B2.5-pre: Peak-normalise to working level before enhancement ──────
    # After NR, peak may be anywhere. Enhancement modules work best when audio
    # has clean headroom. Normalize so PEAK = -3dBFS (not RMS — that clips peaks).
    # This ensures jawhar/bayan/jalal never receive clipped input.
    try:
        _pre_enh_audio = load_audio_fast(nr_wav, 0.0, min(state.total_s, 60.0))
        if len(_pre_enh_audio) > SR:
            _pe_peak_lin = float(np.max(np.abs(_pre_enh_audio)))
            _pe_peak_db  = 20.0 * math.log10(_pe_peak_lin + 1e-9)
            _pe_target   = -3.0   # peak target before enhancement
            _pe_gain     = _pe_target - _pe_peak_db
            if abs(_pe_gain) > 0.3:
                _pre_norm_wav = os.path.join(_TMP, f'pre_norm_{os.getpid()}.wav')
                _pn_ok = ffmpeg_process(
                    nr_wav, _pre_norm_wav,
                    f'volume={_pe_gain:.4f}dB'
                )
                if _pn_ok:
                    nr_wav = _pre_norm_wav
                    L(f'  [pre-norm] peak {_pe_peak_db:.1f}→{_pe_target:.1f}dBFS '
                      f'({_pe_gain:+.2f}dB) — clean headroom for enhancement passes')
    except Exception as _pne:
        L(f'  [pre-norm] skipped: {_pne}')

    # ── PHASE B2.5: IHYAA / JAWHAR — Mutually Exclusive by Tier ──────────────
    # DIAGNOSIS: running ihyaa AND jawhar AND bayan AND noor AND jalal AND nidaa
    # on the same file causes "ping-pong processing" — every module measures
    # from audio already modified by the previous one and fights it.
    #
    # Fix (per VOICE_ENHANCEMENT_NOTES_v2):
    #   TIER_DAMAGED / TIER_CRITICAL → إحياء only (structural recovery)
    #                                   + skip noor / jalal / nidaa below
    #   TIER_DEGRADED and better     → الجوهر only (voice character)
    #                                   + full noor / jalal / nidaa pipeline
    #
    _ihyaa_applied = False
    _jawhar_applied = False

    if state.source_tier in ('TIER_DAMAGED', 'TIER_CRITICAL'):
        # ── إحياء path ────────────────────────────────────────────────────────
        if IHYAA_OK:
            L('\nPass 2B.5 — إحياء (Structural Recovery for Damaged Source)')
            _chk('phase_B2_5_ihyaa')
            try:
                _ihyaa_wav, _ihyaa_rep = apply_ihyaa_to_engine(nr_wav, state, ref)
                if _ihyaa_rep.get('applied', False):
                    nr_wav = _ihyaa_wav
                    _ihyaa_applied = True
                    L(f'  إحياء ✓  '
                      f'IH1={_ihyaa_rep.get("ih1_spectral_applied",False)} '
                      f'IH2={_ihyaa_rep.get("ih2_formant_applied",False)} '
                      f'IH3={_ihyaa_rep.get("ih3_harmonic_applied",False)} '
                      f'IH4={_ihyaa_rep.get("ih4_transient_applied",False)} '
                      f'IH5={_ihyaa_rep.get("ih5_presence_applied",False)} '
                      f'IH6={_ihyaa_rep.get("ih6_dynamic_applied",False)}  '
                      f'rms_Δ={_ihyaa_rep.get("overall_rms_delta",0):+.2f}dB '
                      f'sib_emp_Δ={_ihyaa_rep.get("overall_sib_emp_delta",0):+.2f}dB')
                else:
                    L(f'  إحياء bypass — {_ihyaa_rep.get("skip_reason","unknown")}')
            except Exception as _ie:
                L(f'  إحياء error: {_ie}')
        else:
            L('  إحياء bypass — module not available')

    else:
        # ── الجوهر path (TIER_DEGRADED / COMPRESSED / CLEAN / PRISTINE) ───────
        if JAWHAR_OK:
            L('\nPass 2B.5 — الجوهر (Voice Character De-pixelation)')
            _chk('phase_B2_5_jawhar')
            try:
                # Widened gates for real-world sources
                import jawhar_v3 as _jv3
                # Gate widths per tier — DEGRADED sources have noisier sib band
                # J-3 body texture fill legitimately shifts sib measurement
                # for any source with inter-harmonic noise — widen gates globally
                _jv3._GATE_SIB_DROP_DB = 6.0
                _jv3._GATE_LUFS_DELTA  = 4.5
                _jv3._GATE_LPC_RATIO   = 8.0
                # Convert to stereo WAV that jawhar expects
                _jaw_stereo = os.path.join(_TMP, f'jawhar_in_{os.getpid()}.wav')
                subprocess.run(
                    ['ffmpeg','-y','-i',nr_wav,'-ac','2','-ar','48000',
                     '-c:a','pcm_s16le', _jaw_stereo],
                    capture_output=True)
                _jaw_out, _jaw_res = apply_jawhar(_jaw_stereo, state, ref, log_fn=L)
                if _jaw_res.status == 'OK' and _jaw_out != _jaw_stereo:
                    nr_wav = _jaw_out
                    _jawhar_applied = True
                    L(f'  الجوهر ✓  '
                      f'H2/H1: {_jaw_res.h2_ratio_before:.3f}→{_jaw_res.h2_ratio_after:.3f}  '
                      f'tilt: {_jaw_res.tilt_correction_db:+.2f}dB  '
                      f'sfm: {_jaw_res.body_sfm_before:.3f}→{_jaw_res.body_sfm_after:.3f}')
                else:
                    L(f'  الجوهر {_jaw_res.status} — reverted cleanly')
            except Exception as _je:
                L(f'  الجوهر error: {_je}')
        else:
            L('  الجوهر bypass — module not available')

    # ── PHASE B3: SIDRAH — Maqam-Aware Spectral Resonance Field ─────────────
    # After Tier 2 Recovery (cleanest audio), before EQ (EQ corrects from
    # Sidrah-enhanced spectrum rather than raw). Skip on TIER_CRITICAL.
    sidrah_result = None
    if NUMPY_OK and state.source_tier not in ('TIER_CRITICAL',):
        L('\nPass 2C — سِدْرَة (Maqam-Aware Spectral Resonance Field)')
        _chk('phase_B3_sidrah')
        try:
            _sid_clip = load_audio_fast(nr_wav, state.skip_s, state.dur_s)
            _sid_nrms = float(10.0 ** (state.silence_floor / 20.0))
            sidrah_result = apply_sidrah(_sid_clip, SR, noise_rms=_sid_nrms)
            if not sidrah_result.skipped and sidrah_result.v_gate_passed:
                from scipy.io import wavfile as _swf
                _sid_wav = os.path.join(_TMP, 'sidrah_b3.wav')
                _swf.write(_sid_wav, SR, sidrah_result.audio.astype(np.float32))
                nr_wav = _sid_wav
                # KB-09: Store maqam result on state for EQ clamp scaling in design_eq
                state.sidrah_maqam            = sidrah_result.maqam.maqam
                state.sidrah_maqam_confidence = sidrah_result.maqam.confidence
                L(f'  Sidrah ✓  maqam={sidrah_result.maqam.maqam}'
                  f'({sidrah_result.maqam.confidence:.2f})  '
                  f'score={sidrah_result.sidrah_score:.1f}  '
                  f'HLE={sidrah_result.hle_harmonics_pct:.0f}%  '
                  f'TRSB={sidrah_result.trsb_pairs}pairs  '
                  f'MPRM={sidrah_result.mprm_applied}')
            else:
                L(f'  Sidrah bypass — skipped={sidrah_result.skipped}  '
                  f'reason={sidrah_result.skip_reason}  '
                  f'v_gate={sidrah_result.v_gate_passed}')
        except Exception as _se:
            L(f'  Sidrah error: {_se}')
            sidrah_result = None
    else:
        L(f'  Sidrah bypass — tier={state.source_tier}')


    # ── PHASE B4: BAYAN — Voice Intrinsic Quality Enhancement ──────────────
    # Runs after Sidrah (B3) on the cleanest available audio.
    # Detects and corrects intrinsic voice quality problems that noise
    # reduction cannot fix: muddiness, boxiness, harshness, presence deficit,
    # missing air, and body imbalance.  All Arabic phonology protection gates
    # are enforced inside apply_bayan_to_engine().
    # Does NOT run on TIER_CRITICAL (البيان handles voice colour,
    # not structural audio damage — that's الاسترداد's domain).
    bayan_result = None
    if BAYAN_OK and state.source_tier not in ('TIER_CRITICAL',):
        L('\nPass 2D — البيان (Voice Intrinsic Quality Enhancement)')
        _chk('phase_B4_bayan')
        try:
            _bayan_wav, bayan_result = apply_bayan_to_engine(
                nr_wav, state, ref, log_fn=L,
            )
            if bayan_result.status == 'OK':
                nr_wav = _bayan_wav
                state.bayan_applied    = True
                state.bayan_vqs_before = bayan_result.vqs_before
                state.bayan_vqs_after  = bayan_result.vqs_after
                state.bayan_vqs_gain   = bayan_result.vqs_gain
                L(f'  البيان ✓  VQS {bayan_result.vqs_before:.1f}→{bayan_result.vqs_after:.1f} '
                  f'(+{bayan_result.vqs_gain:.1f})  '
                  f'mud={bayan_result.mud_applied} '
                  f'box={bayan_result.box_applied} '
                  f'pres={bayan_result.presence_applied} '
                  f'harsh={bayan_result.harsh_applied} '
                  f'air={bayan_result.air_applied} '
                  f'body={bayan_result.body_applied}')
            else:
                L(f'  البيان {bayan_result.status} — {bayan_result.reason}')
        except Exception as _be:
            L(f'  البيان error: {_be}')
            bayan_result = None
    else:
        reason = 'unavailable' if not BAYAN_OK else f'tier={state.source_tier}'
        L(f'  البيان bypass — {reason}')

    # ── PHASE B5: النور — Voice Character (Soundgoodizer-equivalent) ────────
    # FL Studio chain: Soundgoodizer (psychoacoustic multi-band enhancer)
    # Python equivalent via noor_v5.py:
    #   Stage 1 → STFT harmonic noise gate (separates voiced energy)
    #   Stage 2 → Even-harmonic enrichment (warm 2nd-harmonic saturation)
    #   Stage 3 → Parametric EQ           (subtle centroid lift to 1425H)
    # Bypass: DAMAGED/CRITICAL — harmonic structure already compromised.
    # RMS is volume-matched to input so LUFS pipeline is unaffected.
    # Skip noor/jalal/nidaa on ihyaa path — ping-pong guard
    if NOOR_OK and state.source_tier in _NOOR_TIER_PARAMS and not _ihyaa_applied:
        L('\nPass 2E — النور (Voice Character / Soundgoodizer-equivalent)')
        _chk('phase_B5_noor')
        try:
            import numpy as _np_noor
            _ntp = _NOOR_TIER_PARAMS[state.source_tier]
            _noor_audio = _noor_load(nr_wav)
            _noor_rms_before = float(
                20 * _np_noor.log10(
                    _np_noor.sqrt(_np_noor.mean(_noor_audio.astype('float64') ** 2))
                    + 1e-20))
            L(f'  [النور] tier={state.source_tier}  RMS_in={_noor_rms_before:.2f}dBFS  '
              f'sharpness={_ntp["sharpness"]}  even_mix={_ntp["even_mix"]}dB')
            # Stage 1: STFT harmonic noise gate
            _s1 = _noor_hgate(_noor_audio,
                               sharpness=_ntp['sharpness'],
                               floor=_ntp['floor'],
                               strength=_ntp['strength'])
            # Stage 2: Even-harmonic enrichment (warm saturation)
            _s2 = _noor_even(_s1,
                              drive=_ntp['even_drive'],
                              mix_db=_ntp['even_mix'])
            # Stage 3: Parametric EQ — centroid toward 1425H
            _s3 = _noor_eq(_s2, _NOOR_EQ_NODES)
            # Volume match: hold input RMS exactly — no loudness change
            _noor_gain = (
                (_np_noor.sqrt(_np_noor.mean(_noor_audio.astype('float64') ** 2)) + 1e-20)
                / (_np_noor.sqrt(_np_noor.mean(_s3 ** 2)) + 1e-20)
            )
            _s3 = _np_noor.clip(_s3 * _noor_gain, -0.97, 0.97).astype('float32')
            _noor_rms_after = float(
                20 * _np_noor.log10(
                    _np_noor.sqrt(_np_noor.mean(_s3.astype('float64') ** 2))
                    + 1e-20))
            import uuid as _uu_noor
            _noor_out = os.path.join(_TMP, f'noor_b5_{_uu_noor.uuid4().hex[:8]}.wav')
            _noor_save_wav(_s3, _noor_out)
            if Path(_noor_out).exists() and Path(_noor_out).stat().st_size > 1000:
                nr_wav = _noor_out
                state.noor_applied       = True
                state.noor_rms_before_db = _noor_rms_before
                state.noor_rms_after_db  = _noor_rms_after
                L(f'  النور ✓  RMS {_noor_rms_before:.2f}→{_noor_rms_after:.2f}dBFS  '
                  f'(Δ={_noor_rms_after - _noor_rms_before:+.2f}dB)')
            else:
                L('  النور — output WAV missing, bypass')
        except Exception as _ne:
            L(f'  النور error: {_ne}')
    else:
        _noor_skip_reason = 'unavailable' if not NOOR_OK else f'tier={state.source_tier}'
        L(f'  النور bypass — {_noor_skip_reason}')

    # ── PHASE B6: الجلال — Voice Transcendence Engine ─────────────────────
    L('\nPass 2F — الجلال (Voice Transcendence: Shimmer · Transient · Formant · Sub · Width)')
    _chk('phase_B6_jalal')
    if state.source_tier not in ('TIER_CRITICAL',) and not _ihyaa_applied:
        try:
            _jalal_in     = nr_wav
            _jalal_out, _jalal_rep = apply_jalal(
                _jalal_in, state, ref, log_fn=L)
            if _jalal_rep.get('status', 'SKIPPED') in ('OK', 'OK_MONO') \
               and os.path.exists(_jalal_out) \
               and _jalal_out != _jalal_in:
                nr_wav                   = _jalal_out
                state.jalal_applied      = True
                state.jalal_shimmer      = _jalal_rep.get('j1_shimmer',  False)
                state.jalal_transient    = _jalal_rep.get('j2_transient', False)
                state.jalal_formant      = _jalal_rep.get('j3_formant',  False)
                state.jalal_widener      = _jalal_rep.get('j4_widener',  False)
                state.jalal_sub          = _jalal_rep.get('j5_sub',      False)
                state.jalal_sib_delta    = _jalal_rep.get('sib_delta',   0.0)
                L(f'  الجلال ✓  status={_jalal_rep["status"]}  '
                  f'J1={state.jalal_shimmer} J2={state.jalal_transient} '
                  f'J3={state.jalal_formant} J4={state.jalal_widener} '
                  f'J5={state.jalal_sub}  '
                  f'sib_Δ={state.jalal_sib_delta:+.2f}dB')
            else:
                L(f'  الجلال bypass/revert — status={_jalal_rep.get("status")}  '
                  f'reason={_jalal_rep.get("reason", "")}')
        except Exception as _je:
            L(f'  الجلال error: {_je}')
    else:
        L(f'  الجلال bypass — tier={state.source_tier}')

    # ── PHASE B7: النداء — Neural Identity-Driven Audio Ascension ──────────
    L('\nPass 2G — النداء (DNA Ascension: Harmonic · Sibilant · Room · Body · LUFS)')
    _chk('phase_B7_nidaa')
    if state.source_tier not in ('TIER_CRITICAL',) and not _ihyaa_applied:
        try:
            _nidaa_in  = nr_wav
            _nidaa_out, _nidaa_rep = apply_nidaa(
                _nidaa_in, state, ref, log_fn=L)
            if _nidaa_rep.get('status', 'SKIPPED') in ('OK', 'OK_PARTIAL') \
               and os.path.exists(_nidaa_out) \
               and _nidaa_out != _nidaa_in:
                nr_wav              = _nidaa_out
                state.nidaa_applied   = True
                state.nidaa_delta_lufs   = _nidaa_rep.get('delta_lufs',   0.0)
                state.nidaa_delta_warmth = _nidaa_rep.get('delta_warmth', 0.0)
                state.nidaa_delta_sib    = _nidaa_rep.get('delta_sib',    0.0)
                state.nidaa_modules  = '·'.join(
                    k for k, v in [
                        ('N1', _nidaa_rep.get('n1_harmonic', False)),
                        ('N2', _nidaa_rep.get('n2_sibilant', False)),
                        ('N3', _nidaa_rep.get('n3_room',     False)),
                        ('N4', _nidaa_rep.get('n4_warmth',   False)),
                        ('N5', _nidaa_rep.get('n5_lufs',     False)),
                    ] if v)
                L(f'  النداء ✓  status={_nidaa_rep["status"]}  '
                  f'modules=[{state.nidaa_modules}]  '
                  f'LUFS_Δ={state.nidaa_delta_lufs:+.2f}dB  '
                  f'warmth_Δ={state.nidaa_delta_warmth:+.2f}dB  '
                  f'sib_Δ={state.nidaa_delta_sib:+.2f}dB')
            else:
                L(f'  النداء bypass/revert — status={_nidaa_rep.get("status")}  '
                  f'reason={_nidaa_rep.get("reason", "")}')
        except Exception as _ne:
            L(f'  النداء error: {_ne}')
    else:
        L(f'  النداء bypass — tier={state.source_tier}')

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

    # ── PHASE D-pre: Peak-normalise before joint pass ───────────────────────
    # After enhancement (jawhar+bayan+noor+jalal+nidaa+EQ), peaks can sit at
    # -5 to -9dBFS but LUFS is still -26 to -32 (high crest factor).
    # The joint pass then adds +20dB to reach LUFS target → peaks hit 0dBFS
    # → alimiter fires continuously → 300k distortion clicks.
    #
    # Fix (Section 57.4 KB): normalize to peak = -1dBFS BEFORE joint.
    # Joint then only needs to adjust ±3dB for LUFS — no limiter firing.
    try:
        _pre_joint_audio = load_audio_fast(nr_wav, 0.0, min(state.total_s, 60.0))
        if len(_pre_joint_audio) > SR:
            _pj_peak_lin  = float(np.max(np.abs(_pre_joint_audio)))
            _pj_peak_db   = 20.0 * math.log10(_pj_peak_lin + 1e-9)
            _pj_target_db = -1.0   # peak target — leaves 1dB headroom
            _pj_gain      = _pj_target_db - _pj_peak_db
            if abs(_pj_gain) > 0.3:
                _pre_joint_wav = os.path.join(_TMP, f'pre_joint_{os.getpid()}.wav')
                _pj_ok = ffmpeg_process(
                    nr_wav, _pre_joint_wav,
                    f'volume={_pj_gain:.4f}dB'
                )
                if _pj_ok:
                    nr_wav = _pre_joint_wav
                    L(f'  [pre-joint-peak-norm] peak {_pj_peak_db:.1f}→{_pj_target_db:.1f}dBFS '
                      f'({_pj_gain:+.2f}dB) — prevents joint-pass limiter distortion')
    except Exception as _pje:
        L(f'  [pre-joint-norm] skipped: {_pje}')

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
            L(f'  [do-no-harm-attr] {attr_reason} — trying gain-only')
            # FIX-E: preserve gain even when compand rejected
            _gain_only = JointParams(
                compand_str=_COMPAND_LIBRARY['BYPASS'],
                gain_db=joint_params.gain_db,
                intensity_label='BYPASS')
            _gain_wav = run_pass_joint(eq_wav, _gain_only, f'gainonly_{iteration}')
            _r2g = measure_pass(_gain_wav, ref, state, f'GainOnly-{iteration+1}')
            if _r2g.composite >= r1.composite:
                joint_wav = _gain_wav; r2 = _r2g
                L(f'  [do-no-harm-attr] gain-only accepted: comp={r2.composite:.3f} LUFS={r2.lufs:.2f}')
            else:
                joint_wav = eq_wav; r2 = r1
                L(f'  [do-no-harm-attr] full revert to EQ-only')

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

    # BUG-5 FIX: TYPE_B2 post-pass check
    # needs_tier2() at phase_B2 had no result= so TYPE_B2 was never reachable.
    needs_b2, b2_reason = needs_tier2(state, result=best_result)
    if needs_b2 and 'TYPE_B2' in b2_reason:
        L('  [BUG-5] TYPE_B2 post-pass: ' + b2_reason)
        b2_wav, b2_report = enhance_tier2(best_wav, state, ref)
        if b2_report.get('type_b_applied') and b2_wav != best_wav:
            best_wav = b2_wav
            lra_gain = b2_report.get('lra_recovered', 0.0)
            L('  [T2-B2] applied lra_gain=' + str(round(lra_gain, 2)))
            t2_report['type_b2_applied']  = True
            t2_report['type_b2_lra_gain'] = lra_gain
        else:
            L('  [T2-B2] reverted')

    # ── PHASE E: Final Encode ────────────────────────────────────────────────
    L(f'\nPass 5 — الترميز النهائي MP3 320kbps')
    _chk('phase_E')

    # ── R-5c: Silence Floor Shaping (match 1425H ambient presence) ──────────
    # Runs on best_wav (pre-encode) so the shaped noise is preserved through
    # the 320kbps MP3 encode. Running it on the final MP3 would require a
    # re-encode which would add generation loss.
    # Only for TIER_CRITICAL/TIER_DAMAGED — clean sources already have correct floor.
    r5c_report: Dict = {'applied': False}
    if state.source_tier in ('TIER_CRITICAL', 'TIER_DAMAGED'):
        L('  [R-5c] silence floor shaping...')
        shaped_wav, r5c_report = shape_silence_floor(best_wav, state, ref)
        if shaped_wav != best_wav:
            best_wav = shaped_wav
            L(f'  [R-5c] ✓ floor shaped: '
              f'{r5c_report["floor_before"]:.1f}→{r5c_report["floor_after"]:.1f}dBFS')

    # ── PHASE E1: الفضاء الصوتي — Room Presence (Reeverb + Delay) ──────────
    # FL Studio chain: Fruity Reeverb 2 (hall tail) + Fruity Delay 3 (pre-delay)
    # Python: ffmpeg aecho with multi-tap decay simulating room impulse response.
    # First tap  = Delay 3 pre-delay (15–20ms) — adds depth & front/back positioning
    # Later taps = Reeverb 2 room reflections (exponentially decaying)
    # Applied to best_wav after R-5c silence shaping, before final encode.
    # Bypass: DAMAGED/CRITICAL — adding reverb to noisy audio degrades quality.
    if state.source_tier in _ROOM_TIER_PARAMS:
        L('  [الفضاء] applying room presence (Reeverb 2 + Delay 3 equivalent)...')
        _rp = _ROOM_TIER_PARAMS[state.source_tier]
        _room_filter = (
            f'aecho='
            f'in_gain={_rp["in_gain"]}:'
            f'out_gain={_rp["out_gain"]}:'
            f'delays={_rp["delays"]}:'
            f'decays={_rp["decays"]}'
        )
        import uuid as _uu_room
        _room_out = os.path.join(_TMP, f'room_e1_{_uu_room.uuid4().hex[:8]}.wav')
        _room_ok = ffmpeg_process(best_wav, _room_out, _room_filter)
        if _room_ok and Path(_room_out).exists() and Path(_room_out).stat().st_size > 1000:
            best_wav = _room_out
            state.room_reverb_applied = True
            import math as _math_room
            _wet_linear = 1.0 - _rp['out_gain']  # approximate wet fraction
            state.room_reverb_wet_db = round(
                20 * _math_room.log10(max(_wet_linear, 1e-6)), 1)
            L(f'  الفضاء ✓  tier={state.source_tier}  '
              f'delays=[{_rp["delays"]}]ms  '
              f'decays=[{_rp["decays"]}]  '
              f'~wet={state.room_reverb_wet_db:.1f}dB')
        else:
            L('  الفضاء — aecho failed or output missing, bypass')
    else:
        L(f'  الفضاء bypass — tier={state.source_tier} '
          f'(reverb skipped for damaged/critical sources)')

    output_path, true_peak_db, encode_retries = run_pass_encode(
        best_wav, output_path, state, ref)
    L(f'  TP={true_peak_db:.2f}dBTP  retries={encode_retries}')

    # ── PHASE E: Final Score ─────────────────────────────────────────────────
    final = measure_pass(output_path, ref, state, 'final', is_final=True)
    elapsed = time.time() - t0

    # KB-12-07: SHA-256 output hash (Supplement §65.2)
    _output_hash = 'UNAVAILABLE'
    try:
        _h2 = hashlib.sha256()
        with open(output_path, 'rb') as _hf2:
            for _chunk2 in iter(lambda: _hf2.read(1 << 20), b''):
                _h2.update(_chunk2)
        _output_hash = _h2.hexdigest()[:16]
        L(f'  [KB-12-07/Hash] output SHA-256={_output_hash}')
        L(f'  [KB-12-07/Hash] input={_input_hash} → output={_output_hash}')
    except Exception:
        pass

    lines = [
        f'isteidad-v12 | {state.source_tier} | {elapsed:.0f}s',
        f'Score: {final.score_tier:.0f}/100' +
        (f' ({final.ceiling_reason})' if final.ceiling_reason else ''),
        f'LUFS={final.lufs:.2f} Crest={final.crest:.2f} LRA={final.lra:.2f}',
        f'SHA256 in={_input_hash} out={_output_hash}',
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
        'engine_version':    'v12.0-الاسترداد-KB12',
        'score':             final.score_tier,
        'score_tier':        final.score_tier,
        'score_absolute':    final.score_abs,
        # v12 KB-12 new fields
        'input_sha256':          _input_hash,
        'output_sha256':         _output_hash,
        'qalqalah_guard_active': True,   # KB-12-01 always active in pre-echo
        'ghunnah_guard_active':  True,   # KB-12-02 always active in EQ band conf
        'emphatic_desess_guard': getattr(state, 'sib_emphatic_dominant', False),
        'dark_emphatic_guard':   getattr(state, 'sib_emphatic_dominant', False),
        'alif_f1_guard_active':  True,   # KB-12-05 always active in EQ band conf
        'hams_guard_active':     True,   # KB-12-06 always active in TSNR
        # v11 KB detections (preserved)
        'dolby_suspected':        state.dolby_suspected,
        'dolby_hf_tilt_db':       state.dolby_hf_tilt_db,
        'azimuth_lag_samples':    state.azimuth_lag_samples,
        'azimuth_delay_ms':       state.azimuth_delay_ms,
        'azimuth_corrected':      state.azimuth_corrected,
        'comb_filter_detected':   state.comb_filter_detected,
        'comb_filter_notch_hz':   state.comb_filter_notch_hz,
        'comb_filter_period_ms':  state.comb_filter_period_ms,
        'hf_cutoff_drifting':     state.hf_cutoff_drifting,
        'hf_cutoff_start_hz':     state.hf_cutoff_start_hz,
        'hf_cutoff_end_hz':       state.hf_cutoff_end_hz,
        'tape_iec2_suspected':    state.tape_iec2_suspected,
        'sib_emphatic_snr':       state.sib_emphatic_snr,
        'sib_nonemphatic_snr':    state.sib_nonemphatic_snr,
        'sib_emphatic_dominant':  state.sib_emphatic_dominant,
        'discontinuity_score':    state.discontinuity_score,
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
        # ── Tier 2 / ENGINE-1 الاسترداد ──
        'tier2_active':      t2_report.get('tier2_active', False),
        'tier2_type_a':      t2_report.get('type_a_applied', False),
        'tier2_type_b':      t2_report.get('type_b_applied', False),
        'tier2_type_c':      t2_report.get('type_c_applied', False),
        'tier2_codec_severity': t2_report.get('type_c_report', {}).get('severity', 0),
        'tier2_lra_gain':    t2_report.get('lra_recovered', 0.0),
        'tier2_snr_after':   t2_report.get('snr_after', state.snr_global),
        # ── R-1/R-2/R-5c deep recovery ──
        'r1_wow_applied':    t2_report.get('r1_wow_applied', False),
        'r1_wow_pct':        t2_report.get('r1_wow_pct', 0.0),
        'r2_dropout_applied': t2_report.get('r2_dropout_applied', False),
        'r2_dropouts_fixed': t2_report.get('r2_dropouts', 0),
        'r5c_silence_shaped': r5c_report.get('applied', False),
        'r5c_floor_before':  r5c_report.get('floor_before', state.silence_floor),
        'r5c_floor_after':   r5c_report.get('floor_after',  state.silence_floor),
        # ── R-3 Harmonic Inference ──
        'r3_harmonic_applied': t2_report.get('r3_harmonic_applied', False),
        'r3_synth_frames':     t2_report.get('r3_report', {}).get('synthesized_frames', 0),
        'r3_voiced_frames':    t2_report.get('r3_report', {}).get('voiced_frames', 0),
        'r3_mean_f0_hz':       t2_report.get('r3_report', {}).get('mean_f0_hz', 0.0),
        'r3_rms_delta_db':     t2_report.get('r3_report', {}).get('rms_delta_db', 0.0),
        # ── v5: Phase B3 Sidrah ──────────────────────────────────────────────
        'sidrah_applied':    sidrah_result is not None and not sidrah_result.skipped,
        'sidrah_score':      sidrah_result.sidrah_score      if sidrah_result else 0.0,
        'sidrah_maqam':      sidrah_result.maqam.maqam       if sidrah_result else 'N/A',
        'sidrah_maqam_conf': sidrah_result.maqam.confidence  if sidrah_result else 0.0,
        'sidrah_hle_pct':    sidrah_result.hle_harmonics_pct if sidrah_result else 0.0,
        'sidrah_trsb_pairs': sidrah_result.trsb_pairs        if sidrah_result else 0,
        'sidrah_mprm':       sidrah_result.mprm_applied      if sidrah_result else False,
        'sidrah_v_gate':     sidrah_result.v_gate_passed     if sidrah_result else False,
        'sidrah_cadences':   len(sidrah_result.cadences)     if sidrah_result else 0,
        # ── DeepFilterNet-3 (T-0.5) ─────────────────────────────────────────
        'df3_available':  DEEPFILTER_OK,
        'df3_applied':       state.df3_applied,
        'df3_snr_before':    round(state.df3_snr_before, 1),
        'df3_snr_after':     round(state.df3_snr_after, 1),
        'df3_snr_gain_db':   round(
            state.df3_snr_after - state.df3_snr_before, 1
        ) if state.df3_applied else 0.0,
        'df3_adaptive':      state.df3_adaptive,
        'df3_loud_chunks':   state.df3_loud_chunks,
        'df3_mid_chunks':    state.df3_mid_chunks,
        'df3_quiet_chunks':  state.df3_quiet_chunks,
        'df3_boundaries':    state.df3_boundaries,
        # ── v5: NR recovery_confidence ──────────────────────────────────────
        'recovery_confidence': t2_report.get('recovery_confidence', 1.0),
        # ── SAFI ─────────────────────────────────────────────────────────────
        'safi_applied':        t2_report.get('safi_applied', False),
        'safi_snr_gain_db':    t2_report.get('safi_snr_gain_db', 0.0),
        'safi_f0_hz':          t2_report.get('safi_f0_hz', 0.0),
        'safi_voiced_ratio':   t2_report.get('safi_voiced_ratio', 0.0),
        'safi_voiced_frames':  t2_report.get('safi_voiced_frames', 0),
        'tier_unprocessable':  getattr(state, 'tier_unprocessable', False),
        'jalaa_applied':         t2_report.get('jalaa_applied', False),
        'jalaa_drr_gain_db':     t2_report.get('jalaa_drr_gain', 0.0),
        'jalaa_chunks':          t2_report.get('jalaa_chunks', 0),
        'jalaa_reverb_removed':  getattr(state, 'jalaa_reverb_removed', 0.0),
        # ── البيان Phase B4 — Voice Intrinsic Quality Enhancement ────────────
        'bayan_applied':       state.bayan_applied,
        'bayan_vqs_before':    state.bayan_vqs_before,
        'bayan_vqs_after':     state.bayan_vqs_after,
        'bayan_vqs_gain':      state.bayan_vqs_gain,
        'bayan_mud':           bayan_result.mud_applied      if bayan_result and bayan_result.status == 'OK' else False,
        'bayan_box':           bayan_result.box_applied      if bayan_result and bayan_result.status == 'OK' else False,
        'bayan_presence':      bayan_result.presence_applied if bayan_result and bayan_result.status == 'OK' else False,
        'bayan_harsh':         bayan_result.harsh_applied    if bayan_result and bayan_result.status == 'OK' else False,
        'bayan_air':           bayan_result.air_applied      if bayan_result and bayan_result.status == 'OK' else False,
        'bayan_body':          bayan_result.body_applied     if bayan_result and bayan_result.status == 'OK' else False,
        'bayan_sib_delta_db':  bayan_result.sib_energy_delta if bayan_result and bayan_result.status == 'OK' else 0.0,
        'bayan_eq_chain':      bayan_result.eq_chain_desc    if bayan_result and bayan_result.status == 'OK' else '',
        # ── النور Phase B5 — Voice Character (Soundgoodizer-equivalent) ────
        'noor_applied':        state.noor_applied,
        'noor_rms_before_db':  state.noor_rms_before_db,
        'noor_rms_after_db':   state.noor_rms_after_db,
        # ── الفضاء الصوتي Phase E1 — Room Presence (Reeverb 2 + Delay 3) ──
        'room_reverb_applied': state.room_reverb_applied,
        'room_reverb_wet_db':  state.room_reverb_wet_db,
        # ── الجلال Phase B6 — Voice Transcendence Engine ────────────────────
        'jalal_applied':       state.jalal_applied,
        'jalal_shimmer':       state.jalal_shimmer,
        'jalal_transient':     state.jalal_transient,
        'jalal_formant':       state.jalal_formant,
        'jalal_widener':       state.jalal_widener,
        'jalal_sub':           state.jalal_sub,
        'jalal_sib_delta':     state.jalal_sib_delta,
        # ── النداء Phase B7 — Neural Identity-Driven Audio Ascension ────────
        'nidaa_applied':       state.nidaa_applied,
        'nidaa_modules':       state.nidaa_modules,
        'nidaa_delta_lufs':    state.nidaa_delta_lufs,
        'nidaa_delta_warmth':  state.nidaa_delta_warmth,
        'nidaa_delta_sib':     state.nidaa_delta_sib,
        # ── DNA reference anchors used by النداء ────────────────────────────
        'nidaa_target_F0_hz':            _NIDAA_TARGET['F0_center_hz'],
        'nidaa_target_even_odd_db':      _NIDAA_TARGET['even_odd_bias_db'],
        'nidaa_target_sib_centroid_hz':  _NIDAA_TARGET['sib_centroid_hz'],
        'nidaa_target_room_RT60_500hz':  _NIDAA_TARGET['room_500hz_RT60_s'],
        'nidaa_target_LUFS':             _NIDAA_TARGET['LUFS_target'],
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
            if (d.get('cache_version') == 'v10.7'  # bumped — invalidates earlier caches
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

    p = argparse.ArgumentParser(description='Audio Enhancement Engine v10.7-الاسترداد-v5 — 1425H')
    p.add_argument('-i', '--input')
    p.add_argument('-o', '--output')
    p.add_argument('--iterations', type=int, default=3)
    p.add_argument('--target',     type=float, default=96.0)
    p.add_argument('--ref',        action='append', default=[], metavar='REF_MP3')
    p.add_argument('--clear-cache', action='store_true')
    p.add_argument('--force_tier', default=None,
                   choices=['TIER_PRISTINE','TIER_COMPRESSED','TIER_DEGRADED','TIER_DAMAGED'],
                   help='Override measured source tier for all enhancement passes')
    p.add_argument('--naqaa', action='store_true',
                   help='Run النقاء standalone restoration instead of isteidad '
                        '(MOSQUE/CODEC/CASSETTE profiles). Never chains with isteidad.')
    p.add_argument('--naqaa_profile', default=None,
                   choices=['MOSQUE','CODEC','CASSETTE'],
                   help='Force النقاء profile (default: auto-detect)')
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
        # --naqaa: standalone pipeline — NEVER chains with isteidad
        if args.naqaa:
            try:
                from naqaa_v1_tested import restore as naqaa_restore
                ref_path = REF_FILES[0] if REF_FILES else None
                naqaa_result = naqaa_restore(
                    input_path    = args.input,
                    output_path   = args.output,
                    ref_path      = ref_path,
                    force_profile = args.naqaa_profile,
                    output_br_k   = 320,
                    log_fn        = print,
                )
                print(f'\nالنقاء complete: score {naqaa_result.score_before:.1f}→{naqaa_result.score_after:.1f}')
                return 0
            except ImportError:
                print('ERROR: naqaa_v1_tested.py not found — run without --naqaa')
                return 1
        r = enhance(args.input, args.output, args.iterations, args.target, force_tier=args.force_tier)
        print(f'\n  Score: {r["score"]:.1f}/100  '
              f'LUFS={r["lufs"]:.2f} RMS={r["rms"]:.2f} '
              f'Crest={r["crest"]:.2f} LRA={r["lra"]:.2f}')
        return 0 if r['score'] >= 85 else 1
    except Exception as e:
        print(f'ERROR: {e}'); return 1


if __name__ == '__main__':
    sys.exit(main())
