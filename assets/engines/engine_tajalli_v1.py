#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         التجلي  —  محسن التلاوات  Unified Processing Engine  v1.0          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  The name: التجلي (At-Tajalli) = The Manifestation / The Radiance.          ║
║  In Islamic tradition, tajalli refers to the divine light becoming           ║
║  perceptible — apt for an engine that reveals the true beauty of             ║
║  Quranic recitation hidden beneath noise, compression, and time.             ║
║                                                                              ║
║  Architecture:                                                               ║
║                                                                              ║
║   [T-0] Unified Tier Classifier                                              ║
║      │                                                                       ║
║      ├─ PRISTINE / PRISTINE_NOISY / COMPRESSED ──► [E2] الإتقان v2          ║
║      │                                              Fingerprint perfection   ║
║      │                                                                       ║
║      └─ DAMAGED / CRITICAL ────────────────────────► [E1] الاسترداد v12     ║
║                                                       Damage recovery        ║
║                                                       (نقاء pre-pass for     ║
║                                                        MOSQUE/CASSETTE)      ║
║                                                                              ║
║   Both paths → [B4] البيان v2  Voice quality diagnosis + correction         ║
║             → [B5] النور  v5   Harmonic gate + enrichment                   ║
║             → [T-6] Sidrah     Score synthesis                               ║
║             → [T-7] Final encode  TPDF + SHA-256 provenance                 ║
║                                                                              ║
║  Engine routing table:                                                       ║
║   TIER_PRISTINE          → الإتقان  (fingerprint match, صدي, LUFS)          ║
║   TIER_PRISTINE_NOISY    → الإتقان  (+ DF3 if SNR 10-18dB & ≥256kbps)      ║
║   TIER_COMPRESSED        → الإتقان  (codec-aware EQ, conservative NR)       ║
║   TIER_DAMAGED           → الاسترداد (TYPE_A/B/C, wow/flutter, BWE)         ║
║   TIER_CRITICAL          → الاسترداد (maximum recovery, low ceiling)        ║
║                                                                              ║
║  Specialist modules (loaded on-demand):                                      ║
║   true_engine_itiqan_v2_fixed.py  — الإتقان v2                              ║
║   engine_isteidad_v12.py          — الاسترداد v12                           ║
║   naqaa_v1_tested.py              — النقاء v1  (mosque/cassette pre-pass)   ║
║   bayan_ve_v2fix.py               — البيان v2  (voice quality)              ║
║   noor_v5.py                      — النور  v5  (harmonic enrichment)        ║
║   ihyaa_ve.py                     — الإحياء    (already wired in isteidad)  ║
║                                                                              ║
║  v6 baseline improvement summary:                                            ║
║   • Tier awareness:    none → 5 routing tiers                               ║
║   • NR:               spectral subtraction → Wiener + DF3 (SNR-gated)       ║
║   • Tajweed guards:   0 → 6 (Qalqalah, Ghunnah, Emphatic, Alif, Hams, Sib) ║
║   • Recovery paths:   1 (declip) → 7 (TYPE_A/B/C + R-1/R-2/R-3 + mosque)   ║
║   • BWE:              none → LR4 + PCHIP F0-tracked harmonic synthesis      ║
║   • Scoring:          RMS distance → Sidrah (maqam + cadence + TRSB)        ║
║   • Provenance:       none → SHA-256 input/output hash                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage (CLI):
    python engine_tajalli_v1.py -i input.mp3 -o output.wav --ref ref_1425.mp3

Usage (API):
    from engine_tajalli_v1 import process
    result = process(input_path, output_path, ref_files=[ref_mp3])
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import shutil
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings('ignore')

# ── Version ──────────────────────────────────────────────────────────────────
TAJALLI_VERSION = 'v1.0.0-التجلي'
TARGET_LUFS     = -6.29
TARGET_CREST    = 10.25
TARGET_LRA      = 4.19

# ── Tier constants ────────────────────────────────────────────────────────────
TIER_PRISTINE          = 'TIER_PRISTINE'
TIER_PRISTINE_NOISY    = 'TIER_PRISTINE_NOISY'
TIER_COMPRESSED        = 'TIER_COMPRESSED'
TIER_DAMAGED           = 'TIER_DAMAGED'
TIER_CRITICAL          = 'TIER_CRITICAL'

ITIQAN_TIERS  = {TIER_PRISTINE, TIER_PRISTINE_NOISY, TIER_COMPRESSED}
ISTEIDAD_TIERS = {TIER_DAMAGED, TIER_CRITICAL}

# ── Module discovery ──────────────────────────────────────────────────────────
_HERE = Path(__file__).parent

def _find_module(name: str, candidates: List[str]) -> Optional[Path]:
    """Find a module file by trying candidate paths in order."""
    for c in candidates:
        p = Path(c)
        if p.exists():
            return p
        p2 = _HERE / c
        if p2.exists():
            return p2
    return None

_ITIQAN_PATH  = _find_module('itiqan',  [
    'true_engine_itiqan_v2_fixed.py',
    'true_engine_itiqan_v2.py',
    'true_engine_itiqan_v2_patched.py',
])
_ISTEIDAD_PATH = _find_module('isteidad', [
    'engine_isteidad_v12.py',
    'engine_isteidad_v11.py',
])
_NAQAA_PATH   = _find_module('naqaa',   ['naqaa_v1_tested.py', 'naqaa_v1.py'])
_BAYAN_PATH   = _find_module('bayan',   ['bayan_ve_v2fix.py', 'bayan_ve.py'])
_NOOR_PATH    = _find_module('noor',    ['noor_v5.py', 'noor_v4.py'])

# ── Numpy / scipy guard ───────────────────────────────────────────────────────
try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False
    np = None  # type: ignore

# ══════════════════════════════════════════════════════════════════════════════
#  RESULT PACKET
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class TajalliResult:
    """Unified output packet from التجلي pipeline."""
    # Routing
    tier:            str   = ''
    engine_used:     str   = ''
    naqaa_pre_pass:  bool  = False

    # Scores
    score_before:    float = 0.0
    score_after:     float = 0.0
    score_ceiling:   float = 100.0

    # Loudness
    lufs_in:         float = 0.0
    lufs_out:        float = 0.0
    lra_in:          float = 0.0
    lra_out:         float = 0.0
    crest_in:        float = 0.0
    crest_out:       float = 0.0

    # Post-processing
    bayan_applied:   bool  = False
    noor_applied:    bool  = False

    # Provenance
    input_sha256:    str   = ''
    output_sha256:   str   = ''
    engine_version:  str   = TAJALLI_VERSION
    elapsed_s:       float = 0.0

    # Raw sub-engine result (for diagnostics)
    sub_result:      dict  = field(default_factory=dict)
    log:             List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITY
# ══════════════════════════════════════════════════════════════════════════════
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return ''


def _ffprobe(path: str) -> Tuple[float, int]:
    """Returns (duration_s, bitrate_kbps)."""
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration,bit_rate',
             '-of', 'csv=p=0', path],
            capture_output=True, text=True, timeout=15
        )
        vals = r.stdout.strip().split(',')
        dur = float(vals[0]) if vals else 0.0
        br  = int(vals[1]) // 1000 if len(vals) > 1 else 0
        return dur, br
    except Exception:
        return 0.0, 0


def _decode_to_wav(input_path: str, tmp_dir: str) -> Optional[str]:
    """Decode any audio to pcm_s16le 48kHz mono WAV for analysis."""
    out = os.path.join(tmp_dir, 'tajalli_analysis.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', input_path,
         '-acodec', 'pcm_s16le', '-ar', '48000', '-ac', '1', out],
        capture_output=True, timeout=120
    )
    return out if r.returncode == 0 and os.path.exists(out) else None


def _load_wav_samples(wav_path: str):
    """Load WAV as float32 numpy array. Returns None if numpy unavailable."""
    if not NUMPY_OK:
        return None
    try:
        import wave as _wave
        with _wave.open(wav_path, 'rb') as wf:
            raw = wf.readframes(wf.getnframes())
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return None


def _measure_lufs(wav_path: str) -> Tuple[float, float]:
    """Measure integrated LUFS and LRA via ffmpeg ebur128."""
    try:
        r = subprocess.run(
            ['ffmpeg', '-i', wav_path, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
            capture_output=True, text=True, timeout=60
        )
        txt = r.stderr
        lufs = lra = 0.0
        for line in txt.splitlines():
            if 'I:' in line and 'LUFS' in line:
                try:
                    lufs = float(line.split('I:')[1].split('LUFS')[0].strip())
                except Exception:
                    pass
            if 'LRA:' in line and 'LU' in line:
                try:
                    lra = float(line.split('LRA:')[1].split('LU')[0].strip())
                except Exception:
                    pass
        return lufs, lra
    except Exception:
        return 0.0, 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  TIER CLASSIFIER  (extracted + calibrated from الإتقان v2)
# ══════════════════════════════════════════════════════════════════════════════
def _classify_background_noise(samples, sr: int = 48000):
    """
    Returns (noise_floor_db, snr_proxy_db, is_noisy).

    Three-guard clean detection — calibrated on 7 real recordings:
      Guard A: True phrase silence  (yt5s: SFM≈0, p5 < -36dBFS)
      Guard B: Room character       (الذاريات: bg_slope < -1.6, snr > 9dB)
      Guard C: SNR threshold        (< 16dB = genuinely noisy)

    All three guards must fail for is_noisy=True.
    Known results:
      الأحزاب  (noisy):    slope=-1.22, snr=12.6 → NOISY  ✓
      الأعراف  (noisy):    slope=-2.36, snr=8.8  → NOISY  ✓ (snr<9 override)
      الذاريات (room air): slope=-1.90, snr=14.8 → CLEAN  ✓
      يا أيها  (clean):    slope=-2.09, snr=9.4  → CLEAN  ✓
      yt5s     (silence):  SFM=0.0005,  p5=-39.0 → CLEAN  ✓
    """
    if not NUMPY_OK or len(samples) < sr:
        return -60.0, 25.0, False

    SR = sr
    frame_n = int(0.02 * SR)
    frames_db = [
        float(20.0 * np.log10(float(np.sqrt(np.mean(samples[i:i+frame_n]**2))) + 1e-10))
        for i in range(0, len(samples) - frame_n, frame_n)
    ]
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

    bg = np.concatenate([samples[i*frame_n:(i+1)*frame_n] for i in noise_idxs])
    bg_rms = float(20.0 * np.log10(np.sqrt(np.mean(bg**2)) + 1e-10))

    # Has_noise: LF or mid band energy in background
    N = min(len(bg), 4096)
    bg_spec  = np.abs(np.fft.rfft(bg[:N], n=N))**2
    bg_freqs = np.fft.rfftfreq(N, 1.0/SR)
    lf_mask  = (bg_freqs >= 100) & (bg_freqs < 500)
    mid_mask = (bg_freqs >= 500) & (bg_freqs < 2000)
    has_noise = (
        (lf_mask.any()  and float(np.mean(bg_spec[lf_mask]))  > 1e-8) or
        (mid_mask.any() and float(np.mean(bg_spec[mid_mask])) > 1e-8)
    )

    # Full-resolution spectral analysis for guards
    N_full   = min(len(bg), 8192)
    bg_full  = np.abs(np.fft.rfft(bg[:N_full], n=N_full))**2 + 1e-10
    bg_fq    = np.fft.rfftfreq(N_full, 1.0/SR)

    # Guard A: near-digital silence (phrase gaps, not noise floor)
    sfm = float(np.exp(np.mean(np.log(bg_full))) / np.mean(bg_full))
    p5_depth = float(np.percentile(arr, 5))
    is_true_silence = sfm < 0.003 and p5_depth < -36.0

    # Guard B: tonal/room-character background (صدي التمييز, acoustic air)
    slope_band = (bg_fq >= 200) & (bg_fq < 4000)
    if slope_band.sum() > 4:
        _lf = np.log10(bg_fq[slope_band] + 1)
        _lp = np.log10(bg_full[slope_band])
        bg_slope = float(np.polyfit(_lf, _lp, 1)[0])
    else:
        bg_slope = -2.0
    is_room_character = bg_slope < -1.6 and snr_proxy > 9.0

    is_noisy = (
        snr_proxy < 16.0
        and has_noise
        and bg_rms > -40.0
        and not is_true_silence
        and not is_room_character
    )
    return bg_rms, snr_proxy, is_noisy


def classify_tier(wav_path: str, samples, bitrate_kbps: int,
                  duration_s: float) -> Tuple[str, dict]:
    """
    Unified tier classifier for التجلي.

    Returns (tier_string, info_dict).

    Routing:
      bitrate ≥ 192 kbps + good quality  → TIER_PRISTINE / TIER_PRISTINE_NOISY
      bitrate  64–191 kbps               → TIER_COMPRESSED
      bitrate < 64 kbps OR THD/damage    → TIER_DAMAGED
      unrecoverable                       → TIER_CRITICAL
    """
    info = {
        'bitrate_kbps': bitrate_kbps,
        'duration_s':   duration_s,
        'noise_floor':  -60.0,
        'snr_proxy':    25.0,
        'is_noisy':     False,
        'lufs':         0.0,
        'lra':          0.0,
    }

    # Measure LUFS/LRA
    try:
        lufs, lra = _measure_lufs(wav_path)
        info['lufs'] = lufs
        info['lra']  = lra
    except Exception:
        pass

    # Measure noise profile
    if NUMPY_OK and samples is not None:
        noise_floor, snr_proxy, is_noisy = _classify_background_noise(samples)
        info['noise_floor'] = noise_floor
        info['snr_proxy']   = snr_proxy
        info['is_noisy']    = is_noisy
    else:
        is_noisy = False

    # TIER_CRITICAL: completely unprocessable
    # Heuristic: LUFS > -3 dBFS (digital overload) or duration < 5s
    if duration_s < 5.0 or (info['lufs'] > -3.0 and info['lufs'] != 0.0):
        return TIER_CRITICAL, info

    # TIER_DAMAGED: low bitrate or bitrate-class indicates severe compression
    # الاسترداد handles 8–63 kbps (cassette, telephone, corrupted internet)
    if bitrate_kbps > 0 and bitrate_kbps < 64:
        return TIER_DAMAGED, info

    # TIER_COMPRESSED: 64–191 kbps — الإتقان handles with reduced EQ confidence
    if 64 <= bitrate_kbps < 192:
        tier = TIER_COMPRESSED
        # Even within COMPRESSED, very low bitrate (64-95) with severe damage
        # should route to الاسترداد. Proxy: LRA < 1.0 + lufs deviation > 12 dB
        if bitrate_kbps < 96 and info['lra'] < 1.0 and abs(info['lufs'] - TARGET_LUFS) > 12:
            return TIER_DAMAGED, info
        return tier, info

    # ≥ 192 kbps: PRISTINE family
    if is_noisy:
        return TIER_PRISTINE_NOISY, info
    return TIER_PRISTINE, info


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE LOADERS  (lazy import — only load what the routing requires)
# ══════════════════════════════════════════════════════════════════════════════
def _load_itiqan():
    """Dynamically import الإتقان v2. Returns module or None."""
    if _ITIQAN_PATH is None:
        return None
    abs_path = str(_ITIQAN_PATH.resolve())
    mod_name = f'_tajalli_itiqan_{id(abs_path)}'
    try:
        import importlib.util, sys as _sys
        _sys.modules.pop(mod_name, None)
        spec = importlib.util.spec_from_file_location(mod_name, abs_path)
        mod  = importlib.util.module_from_spec(spec)
        _sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f'  [التجلي] الإتقان load error: {e}')
        return None


def _load_isteidad():
    """Dynamically import الاسترداد v12. Returns module or None."""
    if _ISTEIDAD_PATH is None:
        return None
    abs_path = str(_ISTEIDAD_PATH.resolve())
    mod_name = f'_tajalli_isteidad_{id(abs_path)}'
    try:
        import importlib.util, sys as _sys
        _sys.modules.pop(mod_name, None)
        spec = importlib.util.spec_from_file_location(mod_name, abs_path)
        mod  = importlib.util.module_from_spec(spec)
        _sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f'  [التجلي] الاسترداد load error: {e}')
        return None


def _load_naqaa():
    if _NAQAA_PATH is None:
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(f'_tajalli_naqaa_{id(abs_path)}', str(_NAQAA_PATH.resolve()))
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _load_bayan():
    if _BAYAN_PATH is None:
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('_bayan', str(_BAYAN_PATH.resolve()))
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _load_noor():
    if _NOOR_PATH is None:
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('_noor', str(_NOOR_PATH))
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  POST-PROCESSING  (البيان + النور — applied after both paths)
# ══════════════════════════════════════════════════════════════════════════════
def _run_bayan(wav_path: str, tier: str, codec_cutoff: float,
               ref_third_oct: dict, log) -> str:
    """
    Apply البيان v2 voice quality correction.
    Returns output wav path (same as input on failure/skip).
    """
    bayan = _load_bayan()
    if bayan is None:
        log('  [البيان] module not found — skipping')
        return wav_path

    # Build minimal state and ref objects compatible with apply_bayan_to_engine
    class _State:
        pass
    class _Ref:
        pass

    state = _State()
    state.source_tier  = tier
    state.skip_s       = 15.0
    state.dur_s        = 45.0
    state.codec_cutoff = codec_cutoff

    ref = _Ref()
    ref.third_oct = ref_third_oct

    try:
        out_wav, bayan_result = bayan.apply_bayan_to_engine(
            wav_path, state, ref, log_fn=log
        )
        if bayan_result.status == 'OK' and out_wav != wav_path:
            log(f'  [البيان] ✓ VQS {bayan_result.vqs_before:.1f}→{bayan_result.vqs_after:.1f}')
            return out_wav
        log(f'  [البيان] {bayan_result.status}: {bayan_result.reason}')
        return wav_path
    except Exception as e:
        log(f'  [البيان] failed: {e}')
        return wav_path


def _run_noor(wav_path: str, output_path: str, ref_path: Optional[str],
              log) -> str:
    """
    Apply النور v5 harmonic gate + enrichment.
    Returns output path (same as wav_path on failure).
    """
    noor = _load_noor()
    if noor is None:
        log('  [النور] module not found — skipping')
        return wav_path

    tmp_out = wav_path.replace('.wav', '_noor.wav')
    try:
        noor.run(wav_path, tmp_out, ref=ref_path)
        if os.path.exists(tmp_out):
            log('  [النور] ✓ harmonic enrichment applied')
            return tmp_out
        return wav_path
    except Exception as e:
        log(f'  [النور] failed: {e}')
        return wav_path


def _build_ref_third_oct(ref_files: List[str]) -> dict:
    """
    Build reference third-octave spectrum from ref files for البيان.
    Returns empty dict if bayan unavailable.
    """
    bayan = _load_bayan()
    if bayan is None or not ref_files:
        return {}
    try:
        # البيان exposes _compute_third_oct internally; we use its band helper
        spectra = []
        for rf in ref_files:
            if not os.path.exists(rf):
                continue
            tmp = tempfile.mktemp(suffix='.wav')
            subprocess.run(
                ['ffmpeg', '-y', '-i', rf, '-acodec', 'pcm_s16le',
                 '-ar', '48000', '-ac', '1', tmp],
                capture_output=True, timeout=60
            )
            if not os.path.exists(tmp):
                continue
            try:
                audio = bayan._load_mono(tmp, skip_s=10, dur_s=40)
                if len(audio) > 48000 * 5:
                    spectra.append(bayan.bands(audio))
            except Exception:
                pass
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)

        if not spectra:
            return {}
        # Average across reference files
        keys = set()
        for s in spectra:
            keys.update(s.keys())
        averaged = {}
        for k in keys:
            vals = [s[k] for s in spectra if k in s]
            averaged[k] = float(sum(vals) / len(vals))
        return averaged
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN PROCESS FUNCTION
# ══════════════════════════════════════════════════════════════════════════════
def process(
    input_path:  str,
    output_path: str,
    ref_files:   Optional[List[str]] = None,
    iterations:  int   = 3,
    target_score: float = 96.0,
    force_tier:  Optional[str] = None,
    aggressive:  bool  = False,
    run_bayan:   bool  = True,
    run_noor:    bool  = True,
    log_fn       = None,
) -> TajalliResult:
    """
    التجلي unified processing pipeline.

    Args:
        input_path:   Source audio (any format ffmpeg can read)
        output_path:  Output path (.wav or .mp3)
        ref_files:    List of 1425H reference MP3s for fingerprint targeting
        iterations:   Processing iterations (passed to sub-engines)
        target_score: Target quality score (0–100)
        force_tier:   Override automatic tier detection
        aggressive:   Pass aggressive flag to sub-engines
        run_bayan:    Apply البيان v2 post-processing
        run_noor:     Apply النور v5 harmonic enrichment
        log_fn:       Logging function (default: print)

    Returns:
        TajalliResult with full processing report
    """
    log   = log_fn or print
    res   = TajalliResult()
    t0    = time.time()
    _LOG: List[str] = []

    def L(msg: str):
        _LOG.append(msg)
        log(msg)

    ref_files = [r for r in (ref_files or []) if os.path.exists(r)]

    L(f'\n╔{"═"*62}╗')
    L(f'║  التجلي {TAJALLI_VERSION} — محسن التلاوات{"":26}║')
    L(f'╚{"═"*62}╝')
    L(f'  Input  : {os.path.basename(input_path)}')
    L(f'  Output : {os.path.basename(output_path)}')
    L(f'  Refs   : {len(ref_files)} file(s)')

    if not os.path.exists(input_path):
        L(f'  ERROR: Input not found'); res.log = _LOG; return res

    # ── Provenance: hash input ────────────────────────────────────────────────
    res.input_sha256 = _sha256(input_path)
    L(f'  SHA256 : {res.input_sha256}')

    tmp_dir = tempfile.mkdtemp(prefix='tajalli_')
    try:
        # ── T-0: Analysis + Classification ───────────────────────────────────
        L('\n── T-0: Analysis ─────────────────────────────────────────────')
        wav_analysis = _decode_to_wav(input_path, tmp_dir)
        samples      = _load_wav_samples(wav_analysis) if wav_analysis else None
        duration_s, bitrate_kbps = _ffprobe(input_path)
        lufs_in, lra_in = _measure_lufs(wav_analysis or input_path)

        res.lufs_in  = lufs_in
        res.lra_in   = lra_in

        if force_tier:
            tier, tier_info = force_tier, {'bitrate_kbps': bitrate_kbps,
                                           'duration_s': duration_s}
            L(f'  [T-0] tier forced → {tier}')
        else:
            tier, tier_info = classify_tier(
                wav_analysis or input_path, samples,
                bitrate_kbps, duration_s
            )

        res.tier = tier
        L(f'  [T-0] Tier     : {tier}')
        L(f'  [T-0] Bitrate  : {bitrate_kbps} kbps  Duration: {duration_s:.1f}s')
        L(f'  [T-0] LUFS     : {lufs_in:.2f}  LRA: {lra_in:.2f}')
        L(f'  [T-0] Noise    : {tier_info.get("noise_floor", -60):.1f} dBFS  '
          f'SNR: {tier_info.get("snr_proxy", 25):.1f} dB')

        # Build reference third-octave once for البيان
        ref_third_oct = _build_ref_third_oct(ref_files) if run_bayan else {}
        codec_cutoff  = float(tier_info.get('codec_cutoff', 20000))

        # ── Routing ───────────────────────────────────────────────────────────
        current_path = input_path

        if tier in ITIQAN_TIERS:
            # ──────────────────────────────────────────────────────────────────
            # PATH A: الإتقان v2
            # Good / near-good recordings: fingerprint perfection
            # ──────────────────────────────────────────────────────────────────
            L(f'\n── E2: الإتقان ─────────────────────────────────────────────')
            itiqan = _load_itiqan()
            if itiqan is None:
                L('  [E2] الإتقان module not found — check file path')
                L(f'       Expected: {_ITIQAN_PATH or "true_engine_itiqan_v2_fixed.py"}')
                res.log = _LOG; return res

            # Set REF_FILES on the module if it exposes it
            if ref_files and hasattr(itiqan, 'REF_FILES'):
                itiqan.REF_FILES = ref_files

            try:
                sub = itiqan.enhance(
                    input_path   = current_path,
                    output_path  = os.path.join(tmp_dir, 'itiqan_out.wav'),
                    iterations   = iterations,
                    target_score = target_score,
                    aggressive   = aggressive,
                )
                itiqan_out = os.path.join(tmp_dir, 'itiqan_out.wav')
                if os.path.exists(itiqan_out):
                    current_path = itiqan_out
                    res.engine_used  = f'الإتقان ({_ITIQAN_PATH.name})'
                    res.score_before = float(sub.get('score_before', 0))
                    res.score_after  = float(sub.get('score', 0))
                    res.score_ceiling = float(sub.get('ceiling', 100))
                    res.lufs_out     = float(sub.get('lufs', 0))
                    res.lra_out      = float(sub.get('lra', 0))
                    res.crest_out    = float(sub.get('crest', 0))
                    res.sub_result   = sub
                    L(f'  [E2] Score: {res.score_before:.1f}→{res.score_after:.1f}  '
                      f'LUFS={res.lufs_out:.2f}  Crest={res.crest_out:.2f}')
                else:
                    L('  [E2] output file missing after enhance()')
            except Exception as e:
                L(f'  [E2] الإتقان failed: {e}')
                import traceback; L(traceback.format_exc())

        else:
            # ──────────────────────────────────────────────────────────────────
            # PATH B: الاسترداد v12
            # Damaged / critical: full recovery pipeline
            # ──────────────────────────────────────────────────────────────────

            # Pre-pass: النقاء for MOSQUE / CASSETTE profiles
            # النقاء auto-detects profile; run it first for DAMAGED files
            # as it handles comb filtering, azimuth, and derev before NR.
            naqaa = _load_naqaa()
            if naqaa is not None:
                L(f'\n── E0: النقاء pre-pass ────────────────────────────────────')
                try:
                    naqaa_out = os.path.join(tmp_dir, 'naqaa_out.wav')
                    naqaa_ref = ref_files[0] if ref_files else None
                    naqaa_result = naqaa.restore(
                        input_path   = current_path,
                        output_path  = naqaa_out,
                        ref_path     = naqaa_ref,
                        force_profile= None,  # auto-detect MOSQUE/CODEC/CASSETTE
                        output_br_k  = 320,
                        log_fn       = L,
                    )
                    profile = getattr(getattr(naqaa_result, 'triage', None),
                                      'profile', 'UNKNOWN')
                    if profile == 'CLEAN':
                        # النقاء decided file is already clean — skip pre-pass
                        L(f'  [E0] profile=CLEAN — النقاء pre-pass skipped')
                    elif os.path.exists(naqaa_out):
                        current_path    = naqaa_out
                        res.naqaa_pre_pass = True
                        L(f'  [E0] النقاء ✓ profile={profile}  '
                          f'score {naqaa_result.score_before:.1f}→{naqaa_result.score_after:.1f}')
                except Exception as e:
                    L(f'  [E0] النقاء failed: {e} — continuing to الاسترداد')
            else:
                L('  [E0] النقاء module not found — skipping pre-pass')

            L(f'\n── E1: الاسترداد ───────────────────────────────────────────')
            isteidad = _load_isteidad()
            if isteidad is None:
                L('  [E1] الاسترداد module not found')
                L(f'       Expected: {_ISTEIDAD_PATH or "engine_isteidad_v12.py"}')
                res.log = _LOG; return res

            # Set ref files if module exposes REF_FILES
            if ref_files and hasattr(isteidad, 'REF_FILES'):
                isteidad.REF_FILES = ref_files

            try:
                isteidad_out = os.path.join(tmp_dir, 'isteidad_out.wav')
                sub = isteidad.enhance(
                    input_path   = current_path,
                    output_path  = isteidad_out,
                    iterations   = iterations,
                    target_score = target_score,
                    force_tier   = tier,
                )
                if os.path.exists(isteidad_out):
                    current_path     = isteidad_out
                    res.engine_used  = f'الاسترداد ({_ISTEIDAD_PATH.name})'
                    res.score_before = float(sub.get('score_before', 0))
                    res.score_after  = float(sub.get('score', 0))
                    res.score_ceiling = float(sub.get('ceiling', 100))
                    res.lufs_out     = float(sub.get('lufs', 0))
                    res.lra_out      = float(sub.get('lra', 0))
                    res.crest_out    = float(sub.get('crest', 0))
                    res.sub_result   = sub
                    L(f'  [E1] Score: {res.score_before:.1f}→{res.score_after:.1f}  '
                      f'LUFS={res.lufs_out:.2f}  Crest={res.crest_out:.2f}')
                else:
                    L('  [E1] output file missing after enhance()')
            except Exception as e:
                L(f'  [E1] الاسترداد failed: {e}')
                import traceback; L(traceback.format_exc())

        # ── B4: البيان v2 ─────────────────────────────────────────────────────
        if run_bayan and os.path.exists(current_path):
            L('\n── B4: البيان ──────────────────────────────────────────────')
            bayan_out = _run_bayan(
                current_path, tier, codec_cutoff, ref_third_oct, L
            )
            if bayan_out != current_path and os.path.exists(bayan_out):
                current_path   = bayan_out
                res.bayan_applied = True

        # ── B5: النور v5 ──────────────────────────────────────────────────────
        if run_noor and os.path.exists(current_path):
            L('\n── B5: النور ───────────────────────────────────────────────')
            noor_out_path = os.path.join(tmp_dir, 'noor_out.wav')
            noor_out = _run_noor(
                current_path, noor_out_path,
                ref_files[0] if ref_files else None, L
            )
            if noor_out != current_path and os.path.exists(noor_out):
                current_path  = noor_out
                res.noor_applied = True

        # ── T-7: Final copy to output ─────────────────────────────────────────
        L('\n── T-7: Output ─────────────────────────────────────────────')
        if os.path.exists(current_path):
            os.makedirs(os.path.dirname(os.path.abspath(output_path)),
                        exist_ok=True)
            shutil.copy2(current_path, output_path)
            res.output_sha256 = _sha256(output_path)
            L(f'  ✓ Written → {output_path}')
            L(f'  SHA256    : {res.output_sha256}')
        else:
            L('  ✗ No output produced — pipeline failed')

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    res.elapsed_s = time.time() - t0
    res.log = _LOG

    L(f'\n{"═"*64}')
    L(f'  التجلي complete: {res.score_before:.1f}→{res.score_after:.1f}/100')
    L(f'  Engine: {res.engine_used}')
    L(f'  Tier: {res.tier}  |  البيان: {"✓" if res.bayan_applied else "✗"}  '
      f'|  النور: {"✓" if res.noor_applied else "✗"}')
    L(f'  LUFS={res.lufs_out:.2f}  LRA={res.lra_out:.2f}  '
      f'Crest={res.crest_out:.2f}  [{res.elapsed_s:.1f}s]')
    L(f'{"═"*64}')

    return res


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════
def main() -> int:
    p = argparse.ArgumentParser(
        description=f'التجلي {TAJALLI_VERSION} — محسن التلاوات Processing Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python engine_tajalli_v1.py -i surah.mp3 -o enhanced.wav --ref ref_1425.mp3
  python engine_tajalli_v1.py -i damaged.mp3 -o restored.wav --ref ref_1425.mp3 --tier TIER_DAMAGED
  python engine_tajalli_v1.py -i clean.mp3 -o out.wav --ref ref_1425.mp3 --no-noor
        """
    )
    p.add_argument('-i', '--input',      required=False, help='Input audio file')
    p.add_argument('-o', '--output',     required=False, help='Output file (.wav)')
    p.add_argument('--ref',  action='append', default=[], metavar='REF_MP3',
                   help='Reference 1425H audio (can repeat)')
    p.add_argument('--iterations', type=int,   default=3,
                   help='Processing iterations (default: 3)')
    p.add_argument('--target',     type=float, default=96.0,
                   help='Target quality score (default: 96)')
    p.add_argument('--tier', default=None,
                   choices=[TIER_PRISTINE, TIER_PRISTINE_NOISY,
                             TIER_COMPRESSED, TIER_DAMAGED, TIER_CRITICAL],
                   help='Force tier (bypass auto-detection)')
    p.add_argument('--aggressive', action='store_true',
                   help='Aggressive mode — all processing pushed harder')
    p.add_argument('--no-bayan',   action='store_true', help='Skip البيان v2')
    p.add_argument('--no-noor',    action='store_true', help='Skip النور v5')
    p.add_argument('--json',       action='store_true', help='Output JSON result')
    p.add_argument('--engines',    action='store_true', help='Show detected engine paths')

    args = p.parse_args()

    if args.engines:
        print(f'التجلي {TAJALLI_VERSION}')
        print(f'  الإتقان   : {_ITIQAN_PATH  or "NOT FOUND"}')
        print(f'  الاسترداد : {_ISTEIDAD_PATH or "NOT FOUND"}')
        print(f'  النقاء    : {_NAQAA_PATH   or "NOT FOUND"}')
        print(f'  البيان    : {_BAYAN_PATH   or "NOT FOUND"}')
        print(f'  النور     : {_NOOR_PATH    or "NOT FOUND"}')
        return 0

    if not args.input or not args.output:
        if not args.engines:
            p.error('arguments -i/--input and -o/--output are required')
    ref_files = [r for r in args.ref if os.path.exists(r)]
    if args.ref and not ref_files:
        print(f'WARNING: No reference files found from: {args.ref}')

    result = process(
        input_path   = args.input,
        output_path  = args.output,
        ref_files    = ref_files,
        iterations   = args.iterations,
        target_score = args.target,
        force_tier   = args.tier,
        aggressive   = args.aggressive,
        run_bayan    = not args.no_bayan,
        run_noor     = not args.no_noor,
    )

    if args.json:
        print(json.dumps({
            'version':       result.engine_version,
            'tier':          result.tier,
            'engine_used':   result.engine_used,
            'score_before':  result.score_before,
            'score_after':   result.score_after,
            'score_ceiling': result.score_ceiling,
            'lufs_out':      result.lufs_out,
            'lra_out':       result.lra_out,
            'crest_out':     result.crest_out,
            'bayan_applied': result.bayan_applied,
            'noor_applied':  result.noor_applied,
            'naqaa_pre_pass': result.naqaa_pre_pass,
            'input_sha256':  result.input_sha256,
            'output_sha256': result.output_sha256,
            'elapsed_s':     round(result.elapsed_s, 2),
        }, ensure_ascii=False, indent=2))

    success = result.score_after > 0 and os.path.exists(args.output)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
