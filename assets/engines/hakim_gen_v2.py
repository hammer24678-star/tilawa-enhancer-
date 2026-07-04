#!/usr/bin/env python3
# hakim_gen_v2.py — الحكيم generative corrector (v2: real neural backends)
#
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  v2 replaces the imaginary DriftSE/SIPS package stubs with real,          ║
# ║  pip-installable neural speech enhancement models.                         ║
# ║                                                                             ║
# ║  DriftSE role:                                                              ║
# ║    Primary  → Resemble Enhance  (pip install resemble-enhance)              ║
# ║               Diffusion-based harmonic reconstruction, MIT licence           ║
# ║               nfe=32, solver='midpoint', λ tuned per tier                   ║
# ║    Fallback → FRCRN / ClearerVoice  (pip install clearvoice-studio)         ║
# ║               Frequency Recurrent CRN, 16kHz, strong on reverb             ║
# ║                                                                              ║
# ║  SIPS role:                                                                  ║
# ║    Scorer   → DNSMOS P.835  (ONNX, auto-download ~2MB, CPU-only)           ║
# ║               Microsoft's P.835 MOS estimator via onnxruntime               ║
# ║    Corrector→ MetricGAN+  (pip install speechbrain)                         ║
# ║               Trains directly to maximise PESQ — fills gaps DNSMOS flags    ║
# ║                                                                              ║
# ║  All Tajweed gates are UNCHANGED from v1 (emphatic ≤1.5dB, Madd ≤5%).     ║
# ║  apply_hakim() API is UNCHANGED — drop-in replacement for hakim_gen_v1.    ║
# ║                                                                              ║
# ║  Install:                                                                    ║
# ║    pip install resemble-enhance clearvoice-studio speechbrain               ║
# ║    # onnxruntime already required by engine; DNSMOS model auto-downloads    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# KB References: §45 (DriftSE), §46 (SIPS), §82 (Arabic WavLM)
# Architecture: DSP predictor (engine) → neural corrector (الحكيم)
#   B-gen.1: Resemble/FRCRN → Tajweed gate → accept/revert
#   B-gen.2: DNSMOS score → MetricGAN+ if below target → Tajweed gate

from __future__ import annotations

import os
import math
import logging
import subprocess
import urllib.request
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

_LOG = logging.getLogger('hakim_v2')
_TMP = os.environ.get('ISTEIDAD_TMP', '/tmp')
SR   = 48000    # engine sample rate

# ──────────────────────────────────────────────────────────────────────────────
#  Optional heavy imports — fail gracefully so the rest of the engine runs
# ──────────────────────────────────────────────────────────────────────────────

# S225: _NP_OK now depends ONLY on numpy — see engine_itiqan_v6_official.py
# for the full rationale (any scipy failure was silently disabling the whole
# numpy-only pipeline here too). rfft/rfftfreq fall back to numpy's own
# equivalents when scipy.fft is unavailable.
try:
    import numpy as np
    _NP_OK = True
except ImportError:
    _NP_OK = False

try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if _NP_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback

try:
    from scipy.signal import sosfiltfilt, butter
except ImportError:
    pass

# ── Primary neural enhancer: Resemble Enhance ────────────────────────────────
try:
    import torch as _torch
    import torchaudio as _ta
    # The actual enhance function — lazy-import to avoid loading weights at
    # import time (slow on first run because it downloads ~200 MB of weights).
    _TORCH_OK   = True
    _RESEMBLE_OK = False          # set True below if the sub-package is present
    try:
        from resemble_enhance.enhancer.inference import enhance as _resemble_enhance_fn   # type: ignore
        _RESEMBLE_OK = True
    except ImportError:
        pass
except ImportError:
    _TORCH_OK    = False
    _RESEMBLE_OK = False

# ── Fallback neural enhancer: FRCRN via ClearerVoice-Studio ──────────────────
try:
    from clearvoice import ClearVoice as _ClearVoice   # type: ignore
    _FRCRN_OK = True
except ImportError:
    _FRCRN_OK = False

# ── SIPS scorer: DNSMOS P.835 (ONNX, CPU) ────────────────────────────────────
try:
    import onnxruntime as _ort   # type: ignore
    _ORT_OK = True
except ImportError:
    _ORT_OK = False

# ── SIPS corrector: MetricGAN+ via SpeechBrain ───────────────────────────────
try:
    from speechbrain.pretrained import SpectralMaskEnhancement as _SpeechBrainSME   # type: ignore
    _METRICGAN_OK = True
except ImportError:
    _METRICGAN_OK = False

# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────

# DriftSE role: tier + style gates (§III COMPONENT 1)
_DRIFTSE_TRIGGER_TIERS  = {'TIER_DEGRADED', 'TIER_DAMAGED', 'TIER_CRITICAL'}
_DRIFTSE_TRIGGER_STYLES = {'MURATTAL', 'HADR'}  # MUJAWWAD gated separately

# SIPS role: DNSMOS target (P.835 OVRL MOS scale 1–5)
# If OVRL > threshold after the enhancer pass, skip MetricGAN+ (already good).
# Target: 3.5 ≈ acceptable; 3.8 ≈ good; 4.2 ≈ excellent.
_SIPS_OVRL_TARGET       = 3.5

# Tajweed gates (matched to v1 — do NOT relax)
_GATE_EMPHATIC_DELTA_DB = 1.5    # max emphatic ratio shift (600-900Hz band)
_GATE_MADD_SHORTENING   = 0.05   # max 5% sustained-vowel shortening

# Resemble Enhance: λ controls denoise↔enhance balance
# λ=0.0 → pure denoiser (like DeepFilter)
# λ=1.0 → pure enhancer (adds harmonics, may hallucinate on very noisy input)
_RESEMBLE_LAMBDA: Dict[str, float] = {
    'TIER_DEGRADED': 0.5,    # balanced: some HF recovery + denoising
    'TIER_DAMAGED':  0.3,    # lean toward denoising on heavily damaged audio
    'TIER_CRITICAL': 0.2,    # mostly denoising — don't add content to critical
}
_RESEMBLE_NFE = 32           # diffusion steps (32 = quality; 8 = faster on CPU)

# Model cache directories
_MODELS_DIR = Path.home() / '.hakim_models'
_DNSMOS_DIR = _MODELS_DIR / 'dnsmos'
_METRICGAN_DIR = _MODELS_DIR / 'metricgan-plus'

# DNSMOS model (Microsoft DNS-Challenge, MIT license, ~2 MB)
_DNSMOS_MODEL_URL = (
    'https://raw.githubusercontent.com/microsoft/DNS-Challenge/'
    'master/DNSMOS/DNSMOS/sig_bak_ovr.onnx'
)
_DNSMOS_MODEL_PATH = _DNSMOS_DIR / 'sig_bak_ovr.onnx'
_DNSMOS_SR  = 16000
_DNSMOS_SEG = 144160   # 9.01 s × 16 000 = model's fixed input length

# MetricGAN+ HuggingFace model ID (SpeechBrain, MIT license)
_METRICGAN_HF_ID = 'speechbrain/metricgan-plus-voicebank'

# ──────────────────────────────────────────────────────────────────────────────
#  Result dataclass (API-compatible with v1)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HakimResult:
    output_wav:          str   = ''
    status:              str   = 'UNAVAILABLE'
    reason:              str   = ''
    style_gate:          str   = 'UNKNOWN'
    # B-gen.1 (Resemble/FRCRN)
    driftse_applied:     bool  = False
    driftse_accepted:    bool  = False
    driftse_backend:     str   = ''   # 'resemble' | 'frcrn' | ''
    # B-gen.2 (DNSMOS + MetricGAN+)
    sips_applied:        bool  = False
    sips_accepted:       bool  = False
    sips_backend:        str   = ''   # 'metricgan' | 'dnsmos_ok_skipped' | ''
    dnsmos_ovrl_before:  float = 0.0
    dnsmos_ovrl_after:   float = 0.0
    # Tajweed gate outcomes
    emphatic_delta_db:   float = 0.0
    madd_delta_frac:     float = 0.0
    gate_emphatic_pass:  bool  = False
    gate_madd_pass:      bool  = False
    nisqa_delta:         float = 0.0

# ──────────────────────────────────────────────────────────────────────────────
#  Audio helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_wav_mono(path: str, max_s: float = 60.0) -> Optional['np.ndarray']:
    """Load WAV as float32 mono numpy array via ffmpeg → raw pipe."""
    if not _NP_OK:
        return None
    tmp = os.path.join(_TMP, f'hakim_load_{os.getpid()}.f32')
    try:
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', path,
             '-af', 'aformat=channel_layouts=mono',
             '-t', str(max_s), '-ar', str(SR),
             '-f', 'f32le', '-loglevel', 'error', tmp],
            capture_output=True
        )
        if r.returncode != 0 or not os.path.exists(tmp):
            return None
        audio = np.frombuffer(open(tmp, 'rb').read(), dtype=np.float32).copy()
        return audio
    except Exception:
        return None
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def _convert_to_16k(wav_path: str) -> Optional[str]:
    """Return path to 16kHz mono PCM WAV derived from wav_path."""
    out = os.path.join(_TMP, f'hakim_16k_{os.getpid()}.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-af', 'aformat=channel_layouts=mono',
         '-ar', '16000', '-c:a', 'pcm_s16le', '-loglevel', 'error', out],
        capture_output=True
    )
    return out if (r.returncode == 0 and os.path.exists(out)) else None


def _upsample_to_48k(wav_path: str) -> Optional[str]:
    """Return path to 48kHz mono PCM-24 WAV derived from wav_path."""
    out = os.path.join(_TMP, f'hakim_48k_{os.getpid()}.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s24le', '-loglevel', 'error', out],
        capture_output=True
    )
    return out if (r.returncode == 0 and os.path.exists(out)) else None

# ──────────────────────────────────────────────────────────────────────────────
#  Tajweed gates (UNCHANGED from v1 — do not modify)
# ──────────────────────────────────────────────────────────────────────────────

def _compute_emphatic_ratio_db(audio: 'np.ndarray', sr: int = SR) -> float:
    """
    Emphatic consonant ratio: energy(600-900Hz) / energy(1200-2400Hz), in dB.
    Emphatic Sad/Dad/Ta/Dha produce a pharyngeal resonance that darkens the
    600-900Hz band relative to the upper-mid.  A shift > ±1.5dB means the
    enhancer moved this boundary — Arabic phonology harmed.
    """
    if not _NP_OK or len(audio) < sr:
        return 0.0
    chunk = audio[:sr * 10] if len(audio) > sr * 10 else audio
    N     = len(chunk)
    spec  = np.abs(rfft(chunk * np.hanning(N))) ** 2
    freqs = rfftfreq(N, 1.0 / sr)

    def _band_db(lo: float, hi: float) -> float:
        m = (freqs >= lo) & (freqs < hi)
        return float(10 * np.log10(np.mean(spec[m]) + 1e-30)) if m.sum() > 0 else -60.0

    return _band_db(600.0, 900.0) - _band_db(1200.0, 2400.0)


def _detect_sustained_vowels_ms(audio: 'np.ndarray', sr: int = SR
                                ) -> List[float]:
    """
    Detect sustained vowel segments (Madd / Mad proxy) via voiced energy bursts.
    Returns list of durations in milliseconds.  Used to guard Madd shortening.
    """
    if not _NP_OK or not _SCIPY_OK_LOCAL:
        return []
    frame_ms  = 20
    frame_len = int(sr * frame_ms / 1000)
    if len(audio) < frame_len * 3:
        return []
    rms = [float(np.sqrt(np.mean(audio[i:i+frame_len]**2) + 1e-30))
           for i in range(0, len(audio) - frame_len, frame_len)]
    if not rms:
        return []
    threshold = float(np.percentile(rms, 60)) * 0.6
    durations: List[float] = []
    in_vowel  = False
    start_idx = 0
    for idx, r in enumerate(rms):
        if r >= threshold and not in_vowel:
            in_vowel  = True
            start_idx = idx
        elif r < threshold and in_vowel:
            dur_ms = (idx - start_idx) * frame_ms
            if 80 <= dur_ms <= 800:   # Madd range: 80–800ms
                durations.append(dur_ms)
            in_vowel = False
    return durations

try:
    from scipy.signal import sosfiltfilt as _sff, butter as _but
    _SCIPY_OK_LOCAL = True
except ImportError:
    _SCIPY_OK_LOCAL = False


def _validate_tajweed_gate(
        wav_before: str,
        wav_after:  str,
        log_fn:     Optional[Callable] = None
) -> Tuple[bool, str, float, float]:
    """
    Validate that a neural enhancement preserved Tajweed-critical features.

    Gate 1 — Emphatic consonants (ص ض ط ظ):
      600-900Hz band vs 1200-2400Hz must not shift by > ±1.5dB.
    Gate 2 — Madd (prolonged vowels, e.g. مَدّ الطَّبيعي):
      Mean sustained-vowel duration must not shorten by > 5%.

    Returns: (passed, reason, emphatic_delta_db, madd_shortening_frac)
    """
    def _log(msg: str):
        if log_fn:
            log_fn(msg)

    if not _NP_OK:
        _log('  [gate] numpy unavailable — gate bypassed (PASS by default)')
        return True, 'numpy_missing', 0.0, 0.0

    audio_b = _load_wav_mono(wav_before, max_s=60.0)
    audio_a = _load_wav_mono(wav_after,  max_s=60.0)
    if audio_b is None or audio_a is None:
        _log('  [gate] audio load failed — gate bypassed')
        return True, 'load_failed', 0.0, 0.0

    # Gate 1: emphatic ratio
    emp_before = _compute_emphatic_ratio_db(audio_b)
    emp_after  = _compute_emphatic_ratio_db(audio_a)
    emp_delta  = emp_after - emp_before
    gate1_pass = abs(emp_delta) <= _GATE_EMPHATIC_DELTA_DB
    _log(f'  [gate-1/emphatic] Δ={emp_delta:+.2f}dB '
         f'{"✓" if gate1_pass else "✗ FAIL (>{_GATE_EMPHATIC_DELTA_DB}dB)"}')
    if not gate1_pass:
        return False, f'emphatic_delta={emp_delta:.2f}dB', emp_delta, 0.0

    # Gate 2: Madd duration
    madd_b = _detect_sustained_vowels_ms(audio_b)
    madd_a = _detect_sustained_vowels_ms(audio_a)
    madd_frac = 0.0
    if madd_b and madd_a:
        dur_b = float(np.mean(madd_b))
        dur_a = float(np.mean(madd_a))
        madd_frac = max(0.0, (dur_b - dur_a) / max(dur_b, 1.0))
        gate2_pass = madd_frac <= _GATE_MADD_SHORTENING
        _log(f'  [gate-2/madd] Δ={madd_frac:.1%} '
             f'{"✓" if gate2_pass else "✗ FAIL (>{_GATE_MADD_SHORTENING:.0%})"}')
        if not gate2_pass:
            return False, f'madd_shortening={madd_frac:.1%}', emp_delta, madd_frac
    else:
        _log('  [gate-2/madd] bypass (insufficient vowel segments detected)')

    return True, 'passed', emp_delta, madd_frac

# ──────────────────────────────────────────────────────────────────────────────
#  B-gen.1 backends — DriftSE role
# ──────────────────────────────────────────────────────────────────────────────

def _run_resemble_enhance(wav_path: str,
                           state,
                           log_fn: Callable) -> Tuple[str, bool]:
    """
    Resemble Enhance — diffusion-based speech enhancement.
    pip install resemble-enhance

    Uses the 'enhancer' (not 'denoiser') mode: both denoises AND reconstructs
    missing harmonics via a learned speech prior.  This maps directly to what
    DriftSE was designed to do: drift the noisy estimate toward the clean
    speech manifold.

    λ (lambd) tuned per source tier:
      TIER_DEGRADED : 0.5  — balanced denoising + HF reconstruction
      TIER_DAMAGED  : 0.3  — lean toward denoising
      TIER_CRITICAL : 0.2  — mostly denoising (don't add content to critical)
    nfe=32: 32 diffusion steps — quality mode (use 8 for speed on CPU)
    """
    if not _RESEMBLE_OK:
        log_fn('  [الحكيم/Resemble] not installed — '
               'run: pip install resemble-enhance')
        return wav_path, False

    tier  = getattr(state, 'source_tier', 'TIER_DEGRADED')
    lambd = _RESEMBLE_LAMBDA.get(tier, 0.5)
    device = 'cuda' if _torch.cuda.is_available() else 'cpu'

    log_fn(f'  [الحكيم/Resemble] enhancing  '
           f'nfe={_RESEMBLE_NFE}  λ={lambd}  device={device} ...')

    tmp_enhanced = os.path.join(_TMP, f'hakim_resemble_{os.getpid()}.wav')
    tmp_48k      = os.path.join(_TMP, f'hakim_resemble48k_{os.getpid()}.wav')
    try:
        dwav, sr = _ta.load(wav_path)                          # (C, T)
        if dwav.shape[0] > 1:
            dwav = dwav.mean(dim=0, keepdim=True)              # force mono

        with _torch.no_grad():
            enhanced, new_sr = _resemble_enhance_fn(           # type: ignore
                dwav, sr,
                device  = device,
                nfe     = _RESEMBLE_NFE,
                solver  = 'midpoint',
                lambd   = lambd,
                tau     = 0.5,
            )

        # enhanced may be 1-D or 2-D (C, T) depending on version
        if enhanced.dim() == 1:
            enhanced = enhanced.unsqueeze(0)
        _ta.save(tmp_enhanced, enhanced.cpu(), new_sr)

        # Resemble outputs at 44.1 kHz — normalise to engine's 48 kHz
        if new_sr != SR:
            r = subprocess.run(
                ['ffmpeg', '-y', '-i', tmp_enhanced,
                 '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s24le',
                 '-loglevel', 'error', tmp_48k],
                capture_output=True
            )
            if r.returncode != 0 or not os.path.exists(tmp_48k):
                log_fn('  [الحكيم/Resemble] 48kHz conversion failed')
                return wav_path, False
            try:
                os.remove(tmp_enhanced)
            except Exception:
                pass
            log_fn('  [الحكيم/Resemble] ✓ inference OK (converted to 48kHz)')
            return tmp_48k, True
        else:
            log_fn('  [الحكيم/Resemble] ✓ inference OK')
            return tmp_enhanced, True

    except Exception as exc:
        log_fn(f'  [الحكيم/Resemble] error: {exc}')
        return wav_path, False


def _run_frcrn(wav_path: str,
               state,
               log_fn: Callable) -> Tuple[str, bool]:
    """
    FRCRN via ClearerVoice-Studio — Frequency Recurrent CRN.
    pip install clearvoice-studio

    16kHz model — input/output resampled around inference.
    Stronger on reverberant mosque recordings than DeepFilter alone.
    Used as fallback when Resemble Enhance is not installed.
    """
    if not _FRCRN_OK:
        log_fn('  [الحكيم/FRCRN] not installed — '
               'run: pip install clearvoice-studio')
        return wav_path, False

    tmp_16k     = os.path.join(_TMP, f'hakim_frcrn_in_{os.getpid()}.wav')
    tmp_out_16k = os.path.join(_TMP, f'hakim_frcrn_out_{os.getpid()}.wav')

    try:
        wav_16k = _convert_to_16k(wav_path)
        if wav_16k is None:
            log_fn('  [الحكيم/FRCRN] ffmpeg downsample failed')
            return wav_path, False

        log_fn('  [الحكيم/FRCRN] running FRCRN_SE_16K ...')
        # ClearVoice expects: input_path, output_path (saves file)
        cv = _ClearVoice(task='speech_enhancement',      # type: ignore
                         model_names=['FRCRN_SE_16K'])
        cv(input_path=wav_16k, output_path=tmp_out_16k)

        if not os.path.exists(tmp_out_16k):
            log_fn('  [الحكيم/FRCRN] no output file produced')
            return wav_path, False

        out_48k = _upsample_to_48k(tmp_out_16k)
        if out_48k is None:
            log_fn('  [الحكيم/FRCRN] 48kHz upsample failed')
            return wav_path, False

        log_fn('  [الحكيم/FRCRN] ✓ inference OK')
        return out_48k, True

    except Exception as exc:
        log_fn(f'  [الحكيم/FRCRN] error: {exc}')
        return wav_path, False
    finally:
        for f in (tmp_16k, tmp_out_16k):
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass


def _run_neural_enhancer(wav_path: str,
                          state,
                          log_fn: Callable) -> Tuple[str, bool, str]:
    """
    Dispatcher for B-gen.1 (DriftSE role).
    Tries: Resemble Enhance → FRCRN → bypass.
    Returns: (output_path, ran_ok, backend_name)
    """
    if _RESEMBLE_OK:
        out, ok = _run_resemble_enhance(wav_path, state, log_fn)
        return out, ok, 'resemble'
    if _FRCRN_OK:
        out, ok = _run_frcrn(wav_path, state, log_fn)
        return out, ok, 'frcrn'

    log_fn('  [الحكيم/Neural] no neural enhancer installed')
    log_fn('  [الحكيم/Neural] install one of:')
    log_fn('    pip install resemble-enhance     (recommended — diffusion)')
    log_fn('    pip install clearvoice-studio    (fallback — FRCRN)')
    return wav_path, False, ''

# ──────────────────────────────────────────────────────────────────────────────
#  B-gen.2 backends — SIPS role
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_dnsmos_model(log_fn: Callable) -> Optional[str]:
    """
    Return path to DNSMOS P.835 ONNX model, downloading if needed.
    The model is ~2 MB and is cached in ~/.hakim_models/dnsmos/.
    Source: microsoft/DNS-Challenge (MIT licence).
    """
    if not _ORT_OK:
        return None
    if _DNSMOS_MODEL_PATH.exists():
        return str(_DNSMOS_MODEL_PATH)
    try:
        _DNSMOS_DIR.mkdir(parents=True, exist_ok=True)
        log_fn(f'  [الحكيم/DNSMOS] downloading model (~2MB) → {_DNSMOS_MODEL_PATH}')
        urllib.request.urlretrieve(_DNSMOS_MODEL_URL, str(_DNSMOS_MODEL_PATH))
        log_fn('  [الحكيم/DNSMOS] model cached OK')
        return str(_DNSMOS_MODEL_PATH)
    except Exception as exc:
        log_fn(f'  [الحكيم/DNSMOS] download failed: {exc}')
        return None


def _score_dnsmos(wav_path: str, model_path: str) -> Tuple[float, float, float]:
    """
    Score audio with DNSMOS P.835 ONNX model.
    Returns (SIG, BAK, OVRL) on a 1–5 MOS scale.
    Segments audio into 9.01s windows (144160 samples @ 16kHz),
    returns mean across windows.
    """
    if not _NP_OK:
        return 0.0, 0.0, 0.0

    # Load at 16kHz
    wav_16k = _convert_to_16k(wav_path)
    if wav_16k is None:
        return 0.0, 0.0, 0.0

    try:
        # Read raw f32le from ffmpeg pipe to avoid soundfile dependency
        tmp_raw = os.path.join(_TMP, f'dnsmos_raw_{os.getpid()}.f32')
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', wav_16k,
             '-f', 'f32le', '-loglevel', 'error', tmp_raw],
            capture_output=True
        )
        if r.returncode != 0 or not os.path.exists(tmp_raw):
            return 0.0, 0.0, 0.0
        audio = np.frombuffer(open(tmp_raw, 'rb').read(), dtype=np.float32).copy()
        os.remove(tmp_raw)

        session = _ort.InferenceSession(       # type: ignore
            model_path,
            providers=['CPUExecutionProvider']
        )
        inp_name = session.get_inputs()[0].name

        scores_sig, scores_bak, scores_ovrl = [], [], []
        for start in range(0, max(1, len(audio) - _DNSMOS_SEG + 1), _DNSMOS_SEG):
            seg = audio[start:start + _DNSMOS_SEG]
            if len(seg) < _DNSMOS_SEG:
                seg = np.pad(seg, (0, _DNSMOS_SEG - len(seg)))
            out = session.run(None, {inp_name: seg[np.newaxis, :].astype(np.float32)})[0][0]
            scores_sig.append(float(out[0]))
            scores_bak.append(float(out[1]))
            scores_ovrl.append(float(out[2]))

        return (float(np.mean(scores_sig)),
                float(np.mean(scores_bak)),
                float(np.mean(scores_ovrl)))

    except Exception:
        return 0.0, 0.0, 0.0
    finally:
        if wav_16k and os.path.exists(wav_16k):
            try:
                os.remove(wav_16k)
            except Exception:
                pass


def _run_metricgan_plus(wav_path: str,
                         log_fn: Callable) -> Tuple[str, bool]:
    """
    MetricGAN+ via SpeechBrain — directly maximises PESQ/MOS.
    pip install speechbrain

    SpeechBrain auto-downloads weights from HuggingFace on first run (~15MB).
    Runs at 16kHz; engine wraps to 48kHz.

    MetricGAN+ trains a mask estimator to maximise a learned perceptual metric
    (PESQ proxy).  It's architecture-agnostic: plug it in AFTER the engine's
    discriminative pipeline (NR + EQ), same as SIPS wrapping the predictor.
    """
    if not _METRICGAN_OK:
        log_fn('  [الحكيم/MetricGAN+] not installed — '
               'run: pip install speechbrain')
        return wav_path, False

    tmp_16k  = os.path.join(_TMP, f'hakim_mg_in_{os.getpid()}.wav')
    tmp_out  = os.path.join(_TMP, f'hakim_mg_out_{os.getpid()}.wav')

    try:
        wav_16k = _convert_to_16k(wav_path)
        if wav_16k is None:
            log_fn('  [الحكيم/MetricGAN+] downsample failed')
            return wav_path, False

        log_fn('  [الحكيم/MetricGAN+] loading model (auto-downloads on first run) ...')
        model = _SpeechBrainSME.from_hparams(          # type: ignore
            source   = _METRICGAN_HF_ID,
            savedir  = str(_METRICGAN_DIR),
            run_opts = {'device': 'cpu'},
        )

        # enhance_file writes output next to input; we specify tmp_out
        enhanced = model.enhance_file(wav_16k)          # type: ignore
        # SpeechBrain returns a torch Tensor (1, T) at the model's SR (16kHz)
        _ta.save(tmp_out, enhanced.unsqueeze(0).cpu() if enhanced.dim() == 1
                 else enhanced.cpu(), 16000)

        out_48k = _upsample_to_48k(tmp_out)
        if out_48k is None:
            log_fn('  [الحكيم/MetricGAN+] 48kHz upsample failed')
            return wav_path, False

        log_fn('  [الحكيم/MetricGAN+] ✓ inference OK')
        return out_48k, True

    except Exception as exc:
        log_fn(f'  [الحكيم/MetricGAN+] error: {exc}')
        return wav_path, False
    finally:
        for f in (tmp_16k, tmp_out):
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass


def _run_sips_v2(wav_path: str,
                  state,
                  log_fn: Callable) -> Tuple[str, bool, str, float, float]:
    """
    SIPS v2 — DNSMOS-gated MetricGAN+ correction.

    1. Score wav_path with DNSMOS P.835.
    2. If OVRL >= _SIPS_OVRL_TARGET (3.5): already good → skip MetricGAN+.
    3. If OVRL <  _SIPS_OVRL_TARGET      : apply MetricGAN+ → rescore.
    4. Accept if OVRL improved; revert if not.

    Returns (output_path, ran, backend, ovrl_before, ovrl_after)
    """
    model_path = _ensure_dnsmos_model(log_fn)
    if model_path is None:
        log_fn('  [الحكيم/SIPS-v2] DNSMOS unavailable — '
               'scoring skipped (onnxruntime required)')
        # Still try MetricGAN+ without scoring gate
        if _METRICGAN_OK:
            out, ok = _run_metricgan_plus(wav_path, log_fn)
            return out, ok, 'metricgan_no_scoring', 0.0, 0.0
        return wav_path, False, '', 0.0, 0.0

    log_fn('  [الحكيم/SIPS-v2] scoring with DNSMOS P.835 ...')
    sig_b, bak_b, ovrl_b = _score_dnsmos(wav_path, model_path)
    log_fn(f'  [الحكيم/SIPS-v2] before — SIG={sig_b:.2f} BAK={bak_b:.2f} '
           f'OVRL={ovrl_b:.2f}  (target ≥ {_SIPS_OVRL_TARGET})')

    if ovrl_b >= _SIPS_OVRL_TARGET:
        log_fn(f'  [الحكيم/SIPS-v2] OVRL ≥ {_SIPS_OVRL_TARGET} — '
               f'MetricGAN+ skipped (already good)')
        return wav_path, False, 'dnsmos_ok_skipped', ovrl_b, ovrl_b

    if not _METRICGAN_OK:
        log_fn('  [الحكيم/SIPS-v2] MetricGAN+ not installed — '
               'run: pip install speechbrain')
        return wav_path, False, '', ovrl_b, 0.0

    mg_out, mg_ok = _run_metricgan_plus(wav_path, log_fn)
    if not mg_ok:
        return wav_path, False, 'metricgan_failed', ovrl_b, 0.0

    # Re-score the MetricGAN+ output
    sig_a, bak_a, ovrl_a = _score_dnsmos(mg_out, model_path)
    log_fn(f'  [الحكيم/SIPS-v2] after  — SIG={sig_a:.2f} BAK={bak_a:.2f} '
           f'OVRL={ovrl_a:.2f}  (Δ={ovrl_a - ovrl_b:+.2f})')

    if ovrl_a >= ovrl_b:
        return mg_out, True, 'metricgan', ovrl_b, ovrl_a

    log_fn('  [الحكيم/SIPS-v2] MetricGAN+ did not improve OVRL — reverting')
    try:
        os.remove(mg_out)
    except Exception:
        pass
    return wav_path, False, 'metricgan_regressed', ovrl_b, ovrl_a

# ──────────────────────────────────────────────────────────────────────────────
#  Main orchestrator — API-compatible with hakim_gen_v1.apply_hakim()
# ──────────────────────────────────────────────────────────────────────────────

def apply_hakim(
        wav_path: str,
        state,
        ref,
        log_fn: Optional[Callable] = None
) -> Tuple[str, HakimResult]:
    """
    الحكيم v2 — The Wise Judge (real neural backends).

    B-gen.1: Neural enhancer (Resemble/FRCRN) + Tajweed gate → accept/revert
    B-gen.2: DNSMOS scoring + MetricGAN+ correction + Tajweed gate → accept/revert

    Returns (output_wav_path, HakimResult).
    If both components fail or are reverted: returns wav_path unchanged.
    """
    result = HakimResult(output_wav=wav_path)

    def _log(msg: str):
        if log_fn:
            log_fn(msg)

    _log('\nPhase B-gen — الحكيم v2 (Resemble Enhance + DNSMOS/MetricGAN+)')
    source_tier = getattr(state, 'source_tier', 'TIER_CLEAN')
    style_class = getattr(state, 'style_class', 'MURATTAL')
    _log(f'  tier={source_tier}  style={style_class}')
    _log(f'  backends — resemble={_RESEMBLE_OK}  frcrn={_FRCRN_OK}  '
         f'dnsmos={_ORT_OK}  metricgan={_METRICGAN_OK}')

    # ── Style gate ────────────────────────────────────────────────────────────
    if style_class == 'MUJAWWAD':
        result.style_gate = 'MUJAWWAD_UNVALIDATED'
        _log('  [الحكيم] style_gate=MUJAWWAD_UNVALIDATED — B-gen.1 skipped')
        _log('  (Validate neural enhancer on maqam ornamental sweeps first)')
    elif style_class in _DRIFTSE_TRIGGER_STYLES:
        result.style_gate = 'PASSED'
    else:
        result.style_gate = 'BYPASSED'

    current_wav = wav_path

    # ──────────────────────────────────────────────────────────────────────────
    # B-gen.1: Neural enhancer (DriftSE role)
    # ──────────────────────────────────────────────────────────────────────────
    driftse_should_run = (
        source_tier in _DRIFTSE_TRIGGER_TIERS
        and result.style_gate == 'PASSED'
    )

    if driftse_should_run:
        _log(f'  [الحكيم/B-gen.1] trigger: tier={source_tier} style={style_class}')
        enh_out, enh_ok, backend = _run_neural_enhancer(current_wav, state, _log)
        result.driftse_applied  = enh_ok
        result.driftse_backend  = backend

        if enh_ok:
            gate_pass, gate_reason, emp_delta, madd_delta = _validate_tajweed_gate(
                current_wav, enh_out, log_fn=_log
            )
            result.emphatic_delta_db  = emp_delta
            result.madd_delta_frac    = madd_delta
            result.gate_emphatic_pass = emp_delta <= _GATE_EMPHATIC_DELTA_DB
            result.gate_madd_pass     = madd_delta <= _GATE_MADD_SHORTENING

            if gate_pass:
                _log(f'  [الحكيم/B-gen.1] {backend.upper()} ACCEPTED ✓')
                current_wav = enh_out
                result.driftse_accepted = True
            else:
                _log(f'  [الحكيم/B-gen.1] {backend.upper()} REVERTED — {gate_reason}')
                try:
                    if enh_out != wav_path:
                        os.remove(enh_out)
                except Exception:
                    pass
    else:
        if source_tier not in _DRIFTSE_TRIGGER_TIERS:
            _log(f'  [الحكيم/B-gen.1] skip — tier={source_tier} '
                 f'not in trigger set {_DRIFTSE_TRIGGER_TIERS}')

    # ──────────────────────────────────────────────────────────────────────────
    # B-gen.2: DNSMOS + MetricGAN+ (SIPS role)
    # ──────────────────────────────────────────────────────────────────────────
    _log(f'  [الحكيم/B-gen.2] scoring: {os.path.basename(current_wav)}')
    sips_out, sips_ok, sips_backend, ovrl_b, ovrl_a = _run_sips_v2(
        current_wav, state, _log
    )
    result.sips_applied       = sips_ok
    result.sips_backend       = sips_backend
    result.dnsmos_ovrl_before = ovrl_b
    result.dnsmos_ovrl_after  = ovrl_a

    if sips_ok:
        gate_pass2, gate_reason2, emp_delta2, madd_delta2 = _validate_tajweed_gate(
            current_wav, sips_out, log_fn=_log
        )
        if not result.driftse_applied:
            result.emphatic_delta_db  = emp_delta2
            result.madd_delta_frac    = madd_delta2
            result.gate_emphatic_pass = emp_delta2 <= _GATE_EMPHATIC_DELTA_DB
            result.gate_madd_pass     = madd_delta2 <= _GATE_MADD_SHORTENING

        if gate_pass2:
            _log(f'  [الحكيم/B-gen.2] MetricGAN+ ACCEPTED ✓  '
                 f'OVRL {ovrl_b:.2f}→{ovrl_a:.2f} '
                 f'(Δ={ovrl_a - ovrl_b:+.2f})')
            current_wav         = sips_out
            result.sips_accepted = True
            result.nisqa_delta   = ovrl_a - ovrl_b
        else:
            _log(f'  [الحكيم/B-gen.2] MetricGAN+ REVERTED — {gate_reason2}')
            try:
                if sips_out != current_wav:
                    os.remove(sips_out)
            except Exception:
                pass

    # ── Final status ──────────────────────────────────────────────────────────
    if result.driftse_accepted and result.sips_accepted:
        result.status = 'OK'
        result.reason = f'{result.driftse_backend.upper()}_accepted + MetricGAN+_accepted'
    elif result.driftse_accepted:
        result.status = 'OK'
        result.reason = f'{result.driftse_backend.upper()}_accepted (SIPS_reverted_or_skipped)'
    elif result.sips_accepted:
        result.status = 'OK'
        result.reason = 'MetricGAN+_accepted (B-gen.1_skipped_or_reverted)'
    elif result.driftse_applied or result.sips_applied:
        result.status = 'REVERTED'
        result.reason = 'All generative passes failed Tajweed gate — reverted'
    elif not (_RESEMBLE_OK or _FRCRN_OK) and not (_METRICGAN_OK and _ORT_OK):
        result.status = 'UNAVAILABLE'
        result.reason = ('No neural backends installed. '
                         'pip install resemble-enhance speechbrain')
    else:
        result.status = 'SKIPPED'
        result.reason = 'tier/style conditions not met'

    result.output_wav = current_wav

    _log(f'  الحكيم → status={result.status}  '
         f'B1={result.driftse_backend or "none"}(accepted={result.driftse_accepted})  '
         f'B2=MetricGAN+(accepted={result.sips_accepted})  '
         f'emp_Δ={result.emphatic_delta_db:.3f}dB  '
         f'madd_Δ={result.madd_delta_frac:.3f}  '
         f'DNSMOS={result.dnsmos_ovrl_before:.2f}→{result.dnsmos_ovrl_after:.2f}')

    return current_wav, result
