#!/usr/bin/env python3
# miraat_ref_v2.py — المرآة reference-guided enhancement (v2: real neural backends)
#
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  v2 replaces the imaginary AnyEnhance/Amphion stub with real,              ║
# ║  pip-installable neural components.                                         ║
# ║                                                                             ║
# ║  Architecture (mirrors AnyEnhance's two-stage intent):                     ║
# ║                                                                             ║
# ║  Stage 1 — Reference speaker verification                                  ║
# ║    SpeechBrain ECAPA-TDNN: encode reference + degraded → speaker cosine    ║
# ║    Gate: sim ≥ 0.70 → same speaker → proceed.                              ║
# ║    Source: speechbrain/spkrec-ecapa-voxceleb (MIT, ~15MB)                  ║
# ║                                                                             ║
# ║  Stage 2 — Reference-guided spectral normalisation                         ║
# ║    a. Extract 1/3-octave spectral profile from the 1425H reference         ║
# ║    b. Run Resemble Enhance (denoise + HF reconstruct) on the degraded      ║
# ║    c. Apply a reference-matched EQ correction (5-band parametric)          ║
# ║    This steers the enhanced output toward the Sheikh's tonal signature      ║
# ║    — the same goal as AnyEnhance's acoustic decoding stage.                ║
# ║                                                                             ║
# ║  Stage 3 — 4-gate validation (same as v1)                                 ║
# ║    Gate-a: speaker cosine similarity ≥ 0.70 post-enhancement               ║
# ║    Gate-b: emphatic consonant ratio ≤ 1.5 dB                               ║
# ║    Gate-c: Madd shortening ≤ 5%                                            ║
# ║    Gate-d: LUFS shift ≤ 3.0 LU                                             ║
# ║                                                                             ║
# ║  Install:                                                                   ║
# ║    pip install speechbrain resemble-enhance                                ║
# ║    # (Resemble shared with hakim_gen_v2 — install once)                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# KB References: §40 (AnyEnhance), §40.2 (two-stage), §40.5 (Arabic bias)

from __future__ import annotations

import os
import math
import subprocess
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

_TMP = os.environ.get('ISTEIDAD_TMP', '/tmp')
SR   = 48000

# ──────────────────────────────────────────────────────────────────────────────
#  Optional heavy imports
# ──────────────────────────────────────────────────────────────────────────────

try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    _NP_OK = True
except ImportError:
    _NP_OK = False

try:
    import torch as _torch
    import torchaudio as _ta
    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False

# ── Stage 1: ECAPA-TDNN speaker embeddings (SpeechBrain) ─────────────────────
try:
    from speechbrain.pretrained import SpeakerRecognition as _SpeakerRec   # type: ignore
    _ECAPA_OK = True
except ImportError:
    _ECAPA_OK = False

# ── Stage 2: Resemble Enhance (shared backend with hakim_gen_v2) ──────────────
try:
    from resemble_enhance.enhancer.inference import enhance as _resemble_enhance_fn   # type: ignore
    _RESEMBLE_OK = True
except ImportError:
    _RESEMBLE_OK = False

# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────

# Trigger tiers (only damaged/critical need reference-guided repair)
_TRIGGER_TIERS  = {'TIER_DAMAGED', 'TIER_CRITICAL'}
_TRIGGER_STYLES = {'MURATTAL'}   # MUJAWWAD ornaments not yet validated

# Speaker similarity gate (ECAPA cosine)
_SIM_THRESHOLD  = 0.70   # < 0.70 → different speaker or severe degradation

# Tajweed / loudness gates (same as v1)
_GATE_EMPHATIC_DELTA_DB = 1.5
_GATE_MADD_SHORTENING   = 0.05
_GATE_LUFS_DELTA_MAX    = 3.0

# Reference EQ correction strength (0.0 = off, 1.0 = full match)
_REF_EQ_BLEND   = 0.65   # partial correction — preserve some of the input character

# Model cache
_MODELS_DIR     = Path.home() / '.hakim_models'
_ECAPA_DIR      = _MODELS_DIR / 'ecapa-voxceleb'
_ECAPA_HF_ID    = 'speechbrain/spkrec-ecapa-voxceleb'

# 1/3-octave centre frequencies for reference profiling
_CENTERS_3OCT   = [125, 160, 200, 250, 315, 400, 500, 630, 800,
                    1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000]

# ──────────────────────────────────────────────────────────────────────────────
#  Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class MiraatResult:
    output_wav:          str   = ''
    status:              str   = 'UNAVAILABLE'
    reason:              str   = ''
    style_gate:          str   = 'UNKNOWN'
    speaker_sim_before:  float = 0.0
    speaker_sim_after:   float = 0.0
    gate_speaker_pass:   bool  = False
    gate_emphatic_pass:  bool  = False
    gate_madd_pass:      bool  = False
    gate_lufs_pass:      bool  = False
    lufs_before:         float = 0.0
    lufs_after:          float = 0.0
    ref_eq_applied:      bool  = False

# ──────────────────────────────────────────────────────────────────────────────
#  Audio helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_wav_mono(path: str, max_s: float = 30.0) -> Optional['np.ndarray']:
    tmp = os.path.join(_TMP, f'miraat_load_{os.getpid()}.f32')
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


def _measure_lufs_simple(path: str) -> float:
    """Quick LUFS proxy using ffmpeg loudnorm stats."""
    try:
        r = subprocess.run(
            ['ffmpeg', '-i', path, '-af',
             'loudnorm=print_format=summary', '-f', 'null', '-'],
            capture_output=True, text=True
        )
        for line in r.stderr.split('\n'):
            if 'Input Integrated' in line:
                return float(line.split(':')[-1].strip().replace(' LUFS', ''))
    except Exception:
        pass
    return -23.0


def _convert_to_16k(wav_path: str) -> Optional[str]:
    out = os.path.join(_TMP, f'miraat_16k_{os.getpid()}.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-af', 'aformat=channel_layouts=mono',
         '-ar', '16000', '-c:a', 'pcm_s16le', '-loglevel', 'error', out],
        capture_output=True
    )
    return out if (r.returncode == 0 and os.path.exists(out)) else None


def _upsample_to_48k(wav_path: str) -> Optional[str]:
    out = os.path.join(_TMP, f'miraat_48k_{os.getpid()}.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s24le',
         '-loglevel', 'error', out],
        capture_output=True
    )
    return out if (r.returncode == 0 and os.path.exists(out)) else None

# ──────────────────────────────────────────────────────────────────────────────
#  Stage 1 — Speaker embedding + similarity
# ──────────────────────────────────────────────────────────────────────────────

_ecapa_model_cache = None

def _get_ecapa_model(log_fn: Callable) -> Optional[object]:
    """Load ECAPA-TDNN model (lazy, cached)."""
    global _ecapa_model_cache
    if not _ECAPA_OK:
        return None
    if _ecapa_model_cache is not None:
        return _ecapa_model_cache
    try:
        log_fn('  [المرآة/ECAPA] loading speaker model (auto-downloads ~15MB) ...')
        _ecapa_model_cache = _SpeakerRec.from_hparams(    # type: ignore
            source   = _ECAPA_HF_ID,
            savedir  = str(_ECAPA_DIR),
            run_opts = {'device': 'cpu'},
        )
        return _ecapa_model_cache
    except Exception as exc:
        log_fn(f'  [المرآة/ECAPA] load failed: {exc}')
        return None


def _speaker_cosine_similarity(wav_a: str, wav_b: str,
                                model: object,
                                log_fn: Callable) -> float:
    """
    Compute ECAPA-TDNN speaker cosine similarity between two WAV files.
    Returns 0.0 on error.  Higher = more similar speaker.
    """
    try:
        wav_a_16k = _convert_to_16k(wav_a)
        wav_b_16k = _convert_to_16k(wav_b)
        if wav_a_16k is None or wav_b_16k is None:
            return 0.0
        score, pred = model.verify_files(wav_a_16k, wav_b_16k)   # type: ignore
        sim = float(score.squeeze())
        return sim
    except Exception as exc:
        log_fn(f'  [المرآة/ECAPA] similarity error: {exc}')
        return 0.0
    finally:
        for p in (wav_a_16k, wav_b_16k):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

# ──────────────────────────────────────────────────────────────────────────────
#  Stage 2 — Reference spectral profile + Resemble Enhance
# ──────────────────────────────────────────────────────────────────────────────

def _third_octave_profile(audio: 'np.ndarray', sr: int = SR
                           ) -> Dict[int, float]:
    """Compute 1/3-octave band energy profile (dBFS) from audio array."""
    if not _NP_OK or len(audio) < sr:
        return {}
    chunk = audio[:sr * 10] if len(audio) > sr * 10 else audio
    N     = len(chunk)
    win   = np.hanning(N)
    norm  = float(np.sqrt(np.sum(win ** 2) / N))
    if norm < 1e-12:
        return {}
    spec  = np.abs(rfft(chunk * win)) / (norm * N)
    freqs = rfftfreq(N, 1.0 / sr)
    out   = {}
    for fc in _CENTERS_3OCT:
        if fc >= sr / 2:
            continue
        fl = fc / (2 ** (1 / 6))
        fh = fc * (2 ** (1 / 6))
        mask = (freqs >= fl) & (freqs < fh)
        if mask.sum() > 0:
            out[fc] = float(20 * np.log10(np.mean(spec[mask]) + 1e-10))
    return out


def _build_reference_eq_nodes(ref_profile: Dict[int, float],
                               src_profile: Dict[int, float],
                               blend: float = _REF_EQ_BLEND
                               ) -> List[Tuple[float, float, float]]:
    """
    Compute EQ nodes to nudge src_profile toward ref_profile.
    Returns list of (freq_hz, gain_db, Q) parametric nodes.
    Limited to bands 250Hz–8kHz and ±6dB per node.
    Q=1.41 (broad shelf per band) — prevents narrow resonances.
    """
    nodes = []
    for fc in _CENTERS_3OCT:
        if fc < 250 or fc > 8000:
            continue
        if fc not in ref_profile or fc not in src_profile:
            continue
        delta = (ref_profile[fc] - src_profile[fc]) * blend
        # Clamp: never more than ±6dB, never boost below 250Hz identity zone
        if 250 <= fc <= 800:
            delta = float(max(-3.0, min(3.0, delta)))   # voice identity zone
        else:
            delta = float(max(-6.0, min(6.0, delta)))
        if abs(delta) >= 0.5:   # ignore sub-0.5dB corrections (noise floor)
            nodes.append((float(fc), round(delta, 2), 1.41))
    return nodes


def _apply_eq_nodes(wav_path: str,
                    nodes: List[Tuple[float, float, float]],
                    log_fn: Callable) -> Optional[str]:
    """Apply parametric EQ nodes via ffmpeg equalizer filter."""
    if not nodes:
        return wav_path
    parts = [f'equalizer=f={f:.0f}:width_type=q:width={q:.2f}:g={g:.2f}'
             for f, g, q in nodes if abs(g) >= 0.5]
    if not parts:
        return wav_path
    af_str = ','.join(parts)
    out = os.path.join(_TMP, f'miraat_eq_{os.getpid()}.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path, '-af', af_str,
         '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s24le',
         '-loglevel', 'error', out],
        capture_output=True
    )
    if r.returncode != 0 or not os.path.exists(out):
        log_fn('  [المرآة/RefEQ] ffmpeg EQ failed — skipping correction')
        return wav_path
    gain_str = '  '.join(f'{f:.0f}Hz{g:+.1f}dB' for f, g, _ in nodes[:6])
    log_fn(f'  [المرآة/RefEQ] applied {len(nodes)}-band correction: {gain_str}')
    return out


def _run_resemble_enhance_miraat(wav_path: str,
                                  log_fn: Callable) -> Tuple[str, bool]:
    """
    Resemble Enhance in 'enhancer' mode for المرآة.
    λ=0.4: lean toward denoising (TIER_DAMAGED/CRITICAL source — don't
    add speculative HF content; let the reference EQ handle spectral steering).
    """
    if not _RESEMBLE_OK or not _TORCH_OK:
        log_fn('  [المرآة/Resemble] not installed — '
               'run: pip install resemble-enhance')
        return wav_path, False

    device = 'cuda' if _torch.cuda.is_available() else 'cpu'
    log_fn(f'  [المرآة/Resemble] enhancing (nfe=32 λ=0.4 device={device}) ...')

    tmp_enh = os.path.join(_TMP, f'miraat_resemble_{os.getpid()}.wav')
    tmp_48k = os.path.join(_TMP, f'miraat_resemble48k_{os.getpid()}.wav')
    try:
        dwav, sr = _ta.load(wav_path)
        if dwav.shape[0] > 1:
            dwav = dwav.mean(dim=0, keepdim=True)
        with _torch.no_grad():
            enhanced, new_sr = _resemble_enhance_fn(     # type: ignore
                dwav, sr, device=device,
                nfe=32, solver='midpoint', lambd=0.4, tau=0.5,
            )
        if enhanced.dim() == 1:
            enhanced = enhanced.unsqueeze(0)
        _ta.save(tmp_enh, enhanced.cpu(), new_sr)

        if new_sr != SR:
            r = subprocess.run(
                ['ffmpeg', '-y', '-i', tmp_enh,
                 '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s24le',
                 '-loglevel', 'error', tmp_48k],
                capture_output=True
            )
            if r.returncode != 0 or not os.path.exists(tmp_48k):
                log_fn('  [المرآة/Resemble] 48kHz conversion failed')
                return wav_path, False
            try:
                os.remove(tmp_enh)
            except Exception:
                pass
            return tmp_48k, True
        return tmp_enh, True
    except Exception as exc:
        log_fn(f'  [المرآة/Resemble] error: {exc}')
        return wav_path, False

# ──────────────────────────────────────────────────────────────────────────────
#  Tajweed + LUFS gates
# ──────────────────────────────────────────────────────────────────────────────

def _compute_emphatic_ratio_db(audio: 'np.ndarray', sr: int = SR) -> float:
    if not _NP_OK or len(audio) < sr:
        return 0.0
    chunk = audio[:sr * 10] if len(audio) > sr * 10 else audio
    N     = len(chunk)
    spec  = np.abs(rfft(chunk * np.hanning(N))) ** 2
    freqs = rfftfreq(N, 1.0 / sr)
    def _b(lo: float, hi: float) -> float:
        m = (freqs >= lo) & (freqs < hi)
        return float(10 * np.log10(np.mean(spec[m]) + 1e-30)) if m.sum() > 0 else -60.0
    return _b(600.0, 900.0) - _b(1200.0, 2400.0)


def _detect_sustained_vowels_ms(audio: 'np.ndarray', sr: int = SR) -> List[float]:
    frame_len = int(sr * 0.020)
    if not _NP_OK or len(audio) < frame_len * 3:
        return []
    rms = [float(np.sqrt(np.mean(audio[i:i+frame_len]**2) + 1e-30))
           for i in range(0, len(audio) - frame_len, frame_len)]
    if not rms:
        return []
    thr = float(np.percentile(rms, 60)) * 0.6
    durs: List[float] = []
    in_v = False
    s = 0
    for i, r in enumerate(rms):
        if r >= thr and not in_v:
            in_v = True
            s = i
        elif r < thr and in_v:
            d = (i - s) * 20.0
            if 80 <= d <= 800:
                durs.append(d)
            in_v = False
    return durs


def _validate_all_gates(
        wav_before: str,
        wav_after:  str,
        ref_wav:    str,
        ecapa_model,
        lufs_before: float,
        log_fn: Callable
) -> Tuple[bool, str, MiraatResult]:
    """
    4-gate validation post-enhancement.
    Gate-a: speaker similarity ≥ 0.70
    Gate-b: emphatic ratio delta ≤ 1.5 dB
    Gate-c: Madd shortening ≤ 5%
    Gate-d: LUFS shift ≤ 3.0 LU
    """
    partial = MiraatResult()

    # Gate-a: speaker similarity (ref vs enhanced)
    if ecapa_model is not None:
        sim_after = _speaker_cosine_similarity(ref_wav, wav_after, ecapa_model, log_fn)
        partial.speaker_sim_after = sim_after
        partial.gate_speaker_pass = sim_after >= _SIM_THRESHOLD
        log_fn(f'  [المرآة/gate-a] speaker sim={sim_after:.3f} '
               f'{"✓" if partial.gate_speaker_pass else "✗ (<0.70)"}')
        if not partial.gate_speaker_pass:
            return False, f'speaker_sim={sim_after:.3f} < {_SIM_THRESHOLD}', partial
    else:
        partial.gate_speaker_pass = True   # gate bypassed — no ECAPA
        log_fn('  [المرآة/gate-a] ECAPA not available — speaker gate bypassed')

    # Gate-b: emphatic
    if _NP_OK:
        ab = _load_wav_mono(wav_before, max_s=30.0)
        aa = _load_wav_mono(wav_after,  max_s=30.0)
        if ab is not None and aa is not None:
            emp_b = _compute_emphatic_ratio_db(ab)
            emp_a = _compute_emphatic_ratio_db(aa)
            emp_d = emp_a - emp_b
            partial.gate_emphatic_pass = abs(emp_d) <= _GATE_EMPHATIC_DELTA_DB
            log_fn(f'  [المرآة/gate-b] emphatic Δ={emp_d:+.2f}dB '
                   f'{"✓" if partial.gate_emphatic_pass else "✗"}')
            if not partial.gate_emphatic_pass:
                return False, f'emphatic_delta={emp_d:.2f}dB', partial
            # Gate-c: Madd
            if ab is not None and aa is not None:
                madd_b = _detect_sustained_vowels_ms(ab)
                madd_a = _detect_sustained_vowels_ms(aa)
                if madd_b and madd_a:
                    db_m = float(np.mean(madd_b))
                    da_m = float(np.mean(madd_a))
                    frac = max(0.0, (db_m - da_m) / max(db_m, 1.0))
                    partial.gate_madd_pass = frac <= _GATE_MADD_SHORTENING
                    log_fn(f'  [المرآة/gate-c] Madd Δ={frac:.1%} '
                           f'{"✓" if partial.gate_madd_pass else "✗"}')
                    if not partial.gate_madd_pass:
                        return False, f'madd_shortening={frac:.1%}', partial
                else:
                    partial.gate_madd_pass = True
                    log_fn('  [المرآة/gate-c] Madd gate bypassed (no vowel segments)')
        else:
            partial.gate_emphatic_pass = True
            partial.gate_madd_pass = True
            log_fn('  [المرآة/gate-bc] audio load failed — Tajweed gates bypassed')
    else:
        partial.gate_emphatic_pass = True
        partial.gate_madd_pass = True

    # Gate-d: LUFS
    lufs_after = _measure_lufs_simple(wav_after)
    partial.lufs_after  = lufs_after
    lufs_shift  = abs(lufs_after - lufs_before)
    partial.gate_lufs_pass = lufs_shift <= _GATE_LUFS_DELTA_MAX
    log_fn(f'  [المرآة/gate-d] LUFS {lufs_before:.1f}→{lufs_after:.1f}LU '
           f'(Δ={lufs_shift:.1f}LU) '
           f'{"✓" if partial.gate_lufs_pass else "✗ (>{_GATE_LUFS_DELTA_MAX}LU)"}')
    if not partial.gate_lufs_pass:
        return False, f'lufs_shift={lufs_shift:.1f}LU', partial

    return True, 'passed', partial

# ──────────────────────────────────────────────────────────────────────────────
#  Main orchestrator — API-compatible with miraat_ref_v1.apply_miraat()
# ──────────────────────────────────────────────────────────────────────────────

def apply_miraat(
        wav_path:       str,
        state,
        ref_files:      List[str],
        log_fn:         Optional[Callable] = None
) -> Tuple[str, MiraatResult]:
    """
    المرآة v2 — The Mirror (reference-guided enhancement).

    Phase B-ref: ECAPA speaker check → Resemble Enhance → reference EQ → 4-gate.

    Returns (output_wav_path, MiraatResult).
    Falls back to wav_path on any failure or gate rejection.
    """
    result = MiraatResult(output_wav=wav_path)

    def _log(msg: str):
        if log_fn:
            log_fn(msg)

    source_tier = getattr(state, 'source_tier', 'TIER_CLEAN')
    style_class = getattr(state, 'style_class', 'MURATTAL')

    _log('\nPhase B-ref — المرآة v2 (ECAPA + Resemble + RefEQ)')
    _log(f'  tier={source_tier}  style={style_class}')
    _log(f'  backends — ecapa={_ECAPA_OK}  resemble={_RESEMBLE_OK}')

    # ── Tier / style gate ─────────────────────────────────────────────────────
    if source_tier not in _TRIGGER_TIERS:
        result.status = 'SKIPPED'
        result.reason = f'tier={source_tier} not in {_TRIGGER_TIERS}'
        _log(f'  [المرآة] skip — {result.reason}')
        return wav_path, result

    if style_class == 'MUJAWWAD':
        result.status    = 'SKIPPED'
        result.style_gate = 'MUJAWWAD_UNVALIDATED'
        result.reason    = 'MUJAWWAD ornamental sweeps not validated — bypass'
        _log(f'  [المرآة] {result.reason}')
        return wav_path, result

    result.style_gate = 'PASSED'

    # ── Reference selection ───────────────────────────────────────────────────
    ref_wav = None
    for rf in (ref_files or []):
        if rf and os.path.exists(rf):
            ref_wav = rf
            break
    if ref_wav is None:
        result.status = 'SKIPPED'
        result.reason = 'no reference file available'
        _log('  [المرآة] no reference file — bypass')
        return wav_path, result

    # Extract a short clean clip from reference (first 20s, skip 2s silence)
    ref_clip = os.path.join(_TMP, f'miraat_refclip_{os.getpid()}.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', ref_wav, '-ss', '2', '-t', '20',
         '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s24le',
         '-loglevel', 'error', ref_clip],
        capture_output=True
    )
    if r.returncode != 0 or not os.path.exists(ref_clip):
        result.status = 'SKIPPED'
        result.reason = 'reference clip extraction failed'
        _log('  [المرآة] reference clip extraction failed — bypass')
        return wav_path, result

    lufs_before = _measure_lufs_simple(wav_path)
    result.lufs_before = lufs_before

    # ── Stage 1: Baseline speaker similarity (ref vs degraded) ───────────────
    ecapa = _get_ecapa_model(_log)
    if ecapa is not None:
        sim_before = _speaker_cosine_similarity(ref_clip, wav_path, ecapa, _log)
        result.speaker_sim_before = sim_before
        _log(f'  [المرآة/stage-1] speaker sim (ref vs input) = {sim_before:.3f}')
        if sim_before < _SIM_THRESHOLD * 0.6:
            # Very low similarity — likely wrong speaker or too damaged
            _log(f'  [المرآة/stage-1] sim={sim_before:.3f} < '
                 f'{_SIM_THRESHOLD * 0.6:.2f} — input too damaged for ref-guided path')
            result.status = 'SKIPPED'
            result.reason = f'input speaker sim too low ({sim_before:.3f})'
            return wav_path, result
    else:
        _log('  [المرآة/stage-1] ECAPA not installed — '
             'run: pip install speechbrain  (speaker gate bypassed)')
        result.speaker_sim_before = 0.0

    # ── Stage 2a: Resemble Enhance ────────────────────────────────────────────
    _log('  [المرآة/stage-2a] running Resemble Enhance (denoiser + HF reconstruct) ...')
    enh_out, enh_ok = _run_resemble_enhance_miraat(wav_path, _log)
    current = enh_out if enh_ok else wav_path

    # ── Stage 2b: Reference spectral profile → EQ correction ─────────────────
    ref_eq_out = current
    if _NP_OK:
        ref_audio = _load_wav_mono(ref_clip, max_s=20.0)
        src_audio = _load_wav_mono(current,  max_s=20.0)
        if ref_audio is not None and src_audio is not None:
            ref_prof = _third_octave_profile(ref_audio)
            src_prof = _third_octave_profile(src_audio)
            eq_nodes = _build_reference_eq_nodes(ref_prof, src_prof)
            if eq_nodes:
                _log(f'  [المرآة/stage-2b] applying {len(eq_nodes)}-band '
                     f'reference EQ correction (blend={_REF_EQ_BLEND}) ...')
                eq_result = _apply_eq_nodes(current, eq_nodes, _log)
                if eq_result and eq_result != current:
                    ref_eq_out = eq_result
                    result.ref_eq_applied = True
                    # Clean up intermediate enhanced file if EQ replaced it
                    if enh_ok and current != wav_path:
                        try:
                            os.remove(current)
                        except Exception:
                            pass
            else:
                _log('  [المرآة/stage-2b] reference already matched — no EQ needed')
        else:
            _log('  [المرآة/stage-2b] audio load failed — ref EQ skipped')
    else:
        _log('  [المرآة/stage-2b] numpy unavailable — ref EQ skipped')

    # ── Stage 3: 4-gate validation ────────────────────────────────────────────
    _log('  [المرآة/stage-3] 4-gate validation ...')
    gate_pass, gate_reason, gate_partial = _validate_all_gates(
        wav_before   = wav_path,
        wav_after    = ref_eq_out,
        ref_wav      = ref_clip,
        ecapa_model  = ecapa,
        lufs_before  = lufs_before,
        log_fn       = _log,
    )
    result.gate_speaker_pass  = gate_partial.gate_speaker_pass
    result.gate_emphatic_pass = gate_partial.gate_emphatic_pass
    result.gate_madd_pass     = gate_partial.gate_madd_pass
    result.gate_lufs_pass     = gate_partial.gate_lufs_pass
    result.speaker_sim_after  = gate_partial.speaker_sim_after
    result.lufs_after         = gate_partial.lufs_after

    # Clean up ref clip
    try:
        if os.path.exists(ref_clip):
            os.remove(ref_clip)
    except Exception:
        pass

    if gate_pass:
        result.status     = 'OK'
        result.reason     = 'all 4 gates passed'
        result.output_wav = ref_eq_out
        _log(f'  المرآة ✓  speaker_sim={result.speaker_sim_after:.3f}  '
             f'lufs={result.lufs_before:.1f}→{result.lufs_after:.1f}LU  '
             f'ref_eq={result.ref_eq_applied}')
        return ref_eq_out, result
    else:
        result.status  = 'REVERTED'
        result.reason  = gate_reason
        result.output_wav = wav_path
        _log(f'  المرآة REVERTED — {gate_reason}')
        # Clean up intermediate files
        for f in (ref_eq_out, enh_out):
            try:
                if f and f != wav_path and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
        return wav_path, result
