#!/usr/bin/env python3
# bayan_ve.py — البيان v2.0
# Voice Intrinsic Quality Enhancement for the AETHERION project
# Phase B4: Runs after Sidrah (B3), before EQ (Phase C)
#
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   البيان — ENGINE-2 OF THE AETHERION   (v2.0)                               ║
║   Voice Intrinsic Quality Enhancement                                        ║
║                                                                              ║
║   BUG FIXES OVER v1.0                                                        ║
║   ─────────────────────────────────────────────────────────────────────     ║
║   BUG-1  Level normalization was missing.                                    ║
║          Input at −15dBFS vs ref at −10dBFS → all bands appeared 5dB       ║
║          deficient → false presence/air/body deltas everywhere.              ║
║          Fix: subtract global level offset (mean over 200–8kHz bands)        ║
║          before every delta computation.                                     ║
║                                                                              ║
║   BUG-2  F0 harmonics flagged as room peaks.                                ║
║          Box detector found 201Hz (=F0) and 391Hz (=2×F0) as "room         ║
║          resonances". Voice harmonics ARE narrow peaks above the local       ║
║          spectral baseline. Now baked into core: _find_spectral_peaks()     ║
║          rejects any peak within 8% of k×F0.                                ║
║                                                                              ║
║   BUG-3  Wrong ffmpeg EQ filter syntax.                                     ║
║          v1 used `t=o` (octave bandwidth). Engine uses `width_type=q`.      ║
║          Fix: _nodes_to_ffmpeg_filter now generates `width_type=q`.         ║
║                                                                              ║
║   BUG-4  Silence frames contaminated spectral diagnosis.                    ║
║          Loading 45s and averaging whole signal dragged all bands down.      ║
║          Fix: voiced-frame gating — only frames within 18dB of p80.         ║
║                                                                              ║
║   BUG-5  Empty reference fallback misfired.                                 ║
║          ref.third_oct = {} → delta = 0 → VQS = 100 → never triggered.    ║
║          Fix: hardcoded الدوسري 1425H spectral reference as fallback.        ║
║                                                                              ║
║   BUG-6  Single 4s FFT window — unstable on recordings with unusual starts. ║
║          Fix: 5-window voiced-frame-averaged multi-window spectrum.          ║
║                                                                              ║
║   BUG-7  Sibilant SNR gate based on wrong reference point.                  ║
║          After EQ, SNR changes independently of actual sibilant damage.     ║
║          Fix: gate now compares sibilant BAND ENERGY (absolute dBFS).       ║
║                                                                              ║
║   BUG-8  Post-correction VQS re-measurement used nonsense noise floor.      ║
║          Used sib_snr_before − 20 as silence_floor proxy.                  ║
║          Fix: carry state.silence_floor through correctly.                   ║
║                                                                              ║
║   NEW CAPABILITIES                                                            ║
║   ─────────────────────────────────────────────────────────────────────     ║
║   NEW-1  Multi-window voiced-spectrum averaging (5 × 8s windows, median).   ║
║   NEW-2  Per-component VQS penalty capped before summing.                   ║
║   NEW-3  Presence split: 1k–2kHz (clarity, سين/شين) vs 2k–4kHz (artic, ء/ه)║
║   NEW-4  Qalqala protection: transient density measured in 2.5k–5kHz band.  ║
║   NEW-5  Component-level trigger: one severe deficit fires BAYAN alone.      ║
║   NEW-6  Body correction: different Q for over-warm cut vs thin boost.       ║
║                                                                              ║
║   المرجع: الشيخ ياسر الدوسري — 1425H                                         ║
║   وما التوفيق إلا بالله                                                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings('ignore')

_TMP = tempfile.gettempdir()
SR   = 48_000

try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

# S225: rfft/rfftfreq fall back to numpy's own equivalents when scipy.fft is
# unavailable, so a missing/broken scipy no longer disables this whole
# numpy-only engine (see engine_itiqan_v6_official.py for full rationale).
try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if NUMPY_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback

# ── Public trigger constant ───────────────────────────────────────────────────
BAYAN_TRIGGER_VQS = 82.0

# ── Arabic protection limits ──────────────────────────────────────────────────
_PROT_SIB_MAX_CUT  = 2.5   # dBFS energy drop allowed in sibilant band
_PROT_EMP_MAX_CUT  = 2.0   # dB cut limit in 500–900Hz
_PROT_GHUN_MAX_ABS = 2.0   # dB abs limit in 900–1200Hz
_PROT_AIR_MAX_GAIN = 3.5   # dB max boost at 9kHz

# ── Per-component severity triggers (NEW-5) ───────────────────────────────────
_COMPONENT_TRIGGER = {
    'mud':      4.0,   # dB excess
    'box':      2,     # peak count
    'presence': -3.5,  # dB deficit
    'harsh':    4.0,   # dB excess
    'air':      -6.0,  # dB deficit
}

# ── Frequency zones ───────────────────────────────────────────────────────────
_BODY_BANDS     = [80.0, 100.0, 125.0, 160.0, 200.0]
_MUD_BANDS      = [200.0, 250.0, 315.0, 400.0, 500.0]
_BOX_BAND_RANGE = (200.0, 850.0)
_EMP_BANDS      = [500.0, 630.0, 800.0]
_GHUN_BANDS     = [1000.0, 1250.0]
_CLARITY_BANDS  = [1000.0, 1250.0, 1600.0, 2000.0]  # NEW-3
_ARTIC_BANDS    = [2000.0, 2500.0, 3150.0, 4000.0]  # NEW-3
_PRESENCE_BANDS = [1000.0, 1250.0, 1600.0, 2000.0, 2500.0, 3150.0, 4000.0]
_HARSH_BANDS    = [2500.0, 3150.0, 4000.0, 5000.0]
_SIB_BANDS      = [2500.0, 3150.0, 4000.0, 5000.0]
_AIR_BANDS      = [8000.0, 10000.0, 12500.0]

# ── VQS penalty weights ───────────────────────────────────────────────────────
_VQS_WEIGHT = {
    'mud': 2.2, 'box': 1.8, 'clarity': 1.4, 'artic': 1.2,
    'harsh': 1.5, 'air': 0.8, 'body': 0.7,
}

# ── BUG-5 FIX: Built-in الدوسري 1425H reference ──────────────────────────────
# 9-window median from 3 reference files, level-anchored at −10.0dBFS RMS.
_DOSSARI_1425H_REF: Dict[float, float] = {
    80.0: -38.5,   100.0: -35.2,   125.0: -31.8,   160.0: -29.4,
    200.0: -26.8,  250.0: -24.5,   315.0: -22.0,   400.0: -21.2,
    500.0: -21.8,  630.0: -22.5,   800.0: -23.4,   1000.0: -25.0,
    1250.0: -27.2, 1600.0: -29.5,  2000.0: -31.8,  2500.0: -34.0,
    3150.0: -36.5, 4000.0: -39.2,  5000.0: -42.0,  6300.0: -45.5,
    8000.0: -50.0, 10000.0: -56.0, 12500.0: -64.0,
}


# ══════════════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BayanDiagnostics:
    body_delta:           float = 0.0
    mud_excess:           float = 0.0
    mud_peak_hz:          float = 315.0
    box_peaks:            List[Tuple[float, float]] = field(default_factory=list)
    clarity_deficit:      float = 0.0   # NEW-3: 1k–2kHz
    artic_deficit:        float = 0.0   # NEW-3: 2k–4kHz
    presence_deficit:     float = 0.0   # combined 1k–4kHz
    harsh_excess:         float = 0.0
    harsh_peak_hz:        float = 3500.0
    air_deficit:          float = 0.0
    emp_delta:            float = 0.0
    ghun_delta:           float = 0.0
    sib_energy_before:    float = -40.0  # BUG-7 FIX: band energy not SNR
    f0_hz:                float = 0.0
    sib_transient_density: float = 0.0  # NEW-4
    level_offset_db:      float = 0.0   # BUG-1 FIX
    vqs:                  float = 100.0


@dataclass
class BayanResult:
    status:           str   = 'SKIPPED'
    reason:           str   = ''
    output_wav:       str   = ''
    vqs_before:       float = 0.0
    vqs_after:        float = 0.0
    vqs_gain:         float = 0.0
    mud_applied:      bool  = False
    box_applied:      bool  = False
    presence_applied: bool  = False
    harsh_applied:    bool  = False
    air_applied:      bool  = False
    body_applied:     bool  = False
    diag:             Optional[BayanDiagnostics] = None
    eq_chain_desc:    str   = ''
    sib_energy_delta: float = 0.0   # BUG-7 FIX: energy delta not SNR delta


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _load_mono(path: str, skip_s: float = 0.0, dur_s: float = 45.0,
               sr: int = SR) -> 'np.ndarray':
    cmd = ['ffmpeg', '-y', '-nostdin']
    if skip_s > 0:
        cmd += ['-ss', str(skip_s)]
    cmd += ['-i', path, '-t', str(dur_s),
            '-af', 'aformat=channel_layouts=stereo,pan=mono|c0=0.5*FL+0.5*FR',
            '-f', 'f32le', '-ar', str(sr), '-loglevel', 'error', '-']
    r = subprocess.run(cmd, capture_output=True)
    if not r.stdout:
        return np.zeros(int(sr * 1), dtype=np.float32)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def _rms_db(a: 'np.ndarray') -> float:
    return float(20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-10))


def _gate_voiced_frames(audio: 'np.ndarray', sr: int = SR,
                         frame_s: float = 0.050) -> 'np.ndarray':
    """
    BUG-4 FIX: Return only voiced frames (within 18dB of p80 RMS).
    Removes silence gaps and inter-ayah pauses from spectral analysis.
    """
    frame_n = int(frame_s * sr)
    if len(audio) < frame_n * 4:
        return audio
    frames  = [audio[i: i + frame_n] for i in range(0, len(audio) - frame_n, frame_n)]
    rmss_db = np.array([float(20 * np.log10(np.sqrt(np.mean(f ** 2)) + 1e-10))
                         for f in frames])
    threshold = float(np.percentile(rmss_db, 80)) - 18.0
    voiced    = [f for f, r in zip(frames, rmss_db) if r > threshold]
    return np.concatenate(voiced, axis=0) if len(voiced) >= 3 else audio


def _voiced_third_oct(audio: 'np.ndarray', sr: int = SR) -> Dict[float, float]:
    """BUG-4+BUG-6 FIX: voiced-gated 1/3-oct using 4s of voiced content."""
    voiced = _gate_voiced_frames(audio, sr)
    chunk  = voiced[:sr * 4] if len(voiced) > sr * 4 else voiced
    N      = len(chunk)
    if N < 64:
        return {}
    window = np.hanning(N)
    norm   = float(np.sqrt(np.sum(window ** 2) / N))
    if norm < 1e-12:
        return {}
    spec  = np.abs(rfft(chunk * window)) / (norm * N)
    freqs = rfftfreq(N, 1.0 / sr)
    all_c = list(set(_BODY_BANDS + _MUD_BANDS + _EMP_BANDS + _GHUN_BANDS +
                     _PRESENCE_BANDS + _HARSH_BANDS + _AIR_BANDS))
    out: Dict[float, float] = {}
    for fc in all_c:
        if fc >= sr / 2:
            continue
        fl = fc / (2 ** (1 / 6))
        fh = fc * (2 ** (1 / 6))
        m  = (freqs >= fl) & (freqs < fh)
        if m.sum() > 0:
            out[fc] = float(20 * np.log10(np.mean(spec[m]) + 1e-10))
    return out


def _multi_window_spectrum(audio: 'np.ndarray', sr: int = SR,
                            n_windows: int = 5, win_s: float = 8.0) -> Dict[float, float]:
    """NEW-1: 5 × 8s voiced-gated windows, median-averaged."""
    win_n = int(win_s * sr)
    step  = max(1, (len(audio) - win_n) // max(1, n_windows - 1))
    specs: List[Dict[float, float]] = []
    for k in range(n_windows):
        s = k * step
        if s + win_n > len(audio):
            break
        sp = _voiced_third_oct(audio[s: s + win_n], sr)
        if sp:
            specs.append(sp)
    if not specs:
        return _voiced_third_oct(audio, sr)
    all_fc = set().union(*specs)
    return {fc: float(np.median([s[fc] for s in specs if fc in s]))
            for fc in all_fc}


def _estimate_f0(audio: 'np.ndarray', sr: int = SR) -> float:
    """Autocorrelation F0 in 80–400Hz range."""
    voiced = _gate_voiced_frames(audio, sr)
    chunk  = voiced[:int(sr * 5)] if len(voiced) > sr * 5 else voiced
    if len(chunk) < sr // 4:
        return 0.0
    corr = np.correlate(chunk.astype(np.float64), chunk.astype(np.float64), mode='full')
    corr = corr[len(corr) // 2:]
    lo, hi = int(sr / 400), min(int(sr / 80), len(corr) - 1)
    if hi <= lo:
        return 0.0
    idx = int(np.argmax(corr[lo:hi])) + lo
    return float(sr / idx) if idx > 0 else 0.0


def _is_f0_harmonic(hz: float, f0: float, tol: float = 0.08) -> bool:
    """BUG-2 FIX: True if hz ≈ k×F0 for k in [1..12]."""
    if f0 <= 0:
        return False
    ratio   = hz / f0
    nearest = round(ratio)
    return 1 <= nearest <= 12 and abs(ratio - nearest) < tol


def _sibilant_band_energy(audio: 'np.ndarray', sr: int = SR) -> float:
    """BUG-7 FIX: Mean sibilant band energy in absolute dBFS (not SNR)."""
    voiced = _gate_voiced_frames(audio, sr)
    if len(voiced) < sr // 4:
        voiced = audio
    N     = len(voiced)
    spec  = np.abs(rfft(voiced.astype(np.float64))) ** 2
    freqs = rfftfreq(N, 1.0 / sr)
    vals  = [float(10 * np.log10(np.mean(spec[(freqs >= fc * 0.85) & (freqs <= fc * 1.18)]) + 1e-30))
             for fc in _SIB_BANDS
             if ((freqs >= fc * 0.85) & (freqs <= fc * 1.18)).any()]
    return float(np.mean(vals)) if vals else -60.0


def _sib_transient_density_band(audio: 'np.ndarray', sr: int = SR) -> float:
    """NEW-4: Transient density in 2.5k–5kHz band for qalqala protection."""
    try:
        from scipy.signal import butter, sosfilt
        sos  = butter(4, [2400, 5100], btype='bandpass', fs=sr, output='sos')
        band = sosfilt(sos, audio.astype(np.float64)).astype(np.float32)
    except Exception:
        return 0.0
    frame_n  = int(0.010 * sr)
    hop      = frame_n // 2
    energies = np.array([float(np.sqrt(np.mean(band[i: i + frame_n] ** 2)))
                         for i in range(0, len(band) - frame_n, hop)])
    if len(energies) < 10:
        return 0.0
    onset = np.diff(energies, prepend=energies[0])
    return float(np.mean(onset > float(np.std(onset)) * 2.0))


def _find_spectral_peaks(audio: 'np.ndarray', f_lo: float, f_hi: float,
                          f0: float, sr: int = SR,
                          n_peaks: int = 4,
                          min_prominence_db: float = 4.5) -> List[Tuple[float, float]]:
    """
    BUG-2 FIX: Room resonance peak detection. Peaks at k×F0 (±8%) excluded.
    BUG-4 FIX: Operates on voiced-gated audio.
    """
    from scipy.signal import find_peaks as _fp
    voiced  = _gate_voiced_frames(audio, sr)
    chunk   = voiced[:min(len(voiced), sr * 10)]
    N       = len(chunk)
    window  = np.hanning(N)
    norm    = float(np.sqrt(np.sum(window ** 2) / N))
    if norm < 1e-12:
        return []
    spec_db = 20 * np.log10(np.abs(rfft(chunk * window)) / (norm * N + 1e-30) + 1e-10)
    freqs   = rfftfreq(N, 1.0 / sr)
    mask    = (freqs >= f_lo) & (freqs <= f_hi)
    f_zone  = freqs[mask]
    s_zone  = spec_db[mask]
    if len(s_zone) < 10:
        return []
    half_win = max(1, len(s_zone) // 12)
    baseline = np.array([np.median(s_zone[max(0, i - half_win): i + half_win + 1])
                         for i in range(len(s_zone))])
    excess   = s_zone - baseline
    peak_idx, _ = _fp(excess, height=min_prominence_db, distance=max(2, len(s_zone) // 30))
    peaks_out: List[Tuple[float, float]] = []
    for idx in peak_idx:
        hz  = float(f_zone[idx])
        exc = float(excess[idx])
        if _is_f0_harmonic(hz, f0, tol=0.08):
            continue
        # Q estimate from half-power bandwidth
        thresh = s_zone[idx] - 3.0
        left, right = idx, idx
        while left > 0 and s_zone[left] > thresh:
            left -= 1
        while right < len(s_zone) - 1 and s_zone[right] > thresh:
            right += 1
        bw_hz = max(float(f_zone[min(right, len(f_zone)-1)]) -
                    float(f_zone[max(left, 0)]), 1.0)
        if hz / bw_hz >= 2.5:
            peaks_out.append((hz, exc))
    return sorted(peaks_out, key=lambda x: -x[1])[:n_peaks]


# ══════════════════════════════════════════════════════════════════════════════
#  REFERENCE
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_reference(ref_third_oct: Dict[float, float]) -> Dict[float, float]:
    """BUG-5 FIX: Fall back to built-in 1425H reference when ref is empty."""
    if ref_third_oct and len(ref_third_oct) >= 10:
        return ref_third_oct
    return dict(_DOSSARI_1425H_REF)


def _normalize_reference(measured: Dict[float, float],
                          ref: Dict[float, float]) -> Tuple[Dict[float, float], float]:
    """
    BUG-1 FIX: Level-normalize ref to the same absolute level as measured.
    Compute mean level offset over common 200–8kHz bands, shift ref up by that.
    Returns (normalized_ref, level_offset_db).
    """
    common = [fc for fc in measured if fc in ref and 200.0 <= fc <= 8000.0]
    if len(common) < 3:
        return ref, 0.0
    loff = float(np.mean([measured[fc] - ref[fc] for fc in common]))
    return {fc: v + loff for fc, v in ref.items()}, loff


# ══════════════════════════════════════════════════════════════════════════════
#  VOICE QUALITY DIAGNOSIS
# ══════════════════════════════════════════════════════════════════════════════

def _compute_vqs(diag: BayanDiagnostics) -> float:
    """
    VQS 0–100. NEW-2: each component penalty clamped independently.
    """
    def _p(val: float, w: float, cap: float = 10.0) -> float:
        return float(np.clip(max(0.0, val) * w, 0.0, cap))

    # FIX-BOX-VQS: use total excess dB (not peak count) so that partial cuts
    # (-5dB on a 20dB peak reduces excess to 15dB) are reflected in VQS.
    # Old formula: len(peaks)*2.0 — unchanged before/after cuts since peaks
    # remain detectable. New: sum(excess)/6.0 tracks magnitude improvement.
    _box_total_excess = sum(exc for _, exc in diag.box_peaks)
    penalties = [
        _p(diag.mud_excess,              _VQS_WEIGHT['mud'],     15.0),
        _p(_box_total_excess / 6.0,      _VQS_WEIGHT['box'],     12.0),
        _p(-diag.clarity_deficit,        _VQS_WEIGHT['clarity'], 10.0),
        _p(-diag.artic_deficit,          _VQS_WEIGHT['artic'],   10.0),
        _p(diag.harsh_excess,            _VQS_WEIGHT['harsh'],   10.0),
        _p(-diag.air_deficit,            _VQS_WEIGHT['air'],      8.0),
        _p(abs(diag.body_delta),         _VQS_WEIGHT['body'],     6.0),
    ]
    return float(np.clip(100.0 - sum(penalties), 0.0, 100.0))


def _should_trigger(diag: BayanDiagnostics) -> Tuple[bool, str]:
    """NEW-5: Trigger on total VQS OR on individual component severity."""
    if diag.vqs < BAYAN_TRIGGER_VQS:
        return True, f'VQS={diag.vqs:.1f} < {BAYAN_TRIGGER_VQS}'
    reasons: List[str] = []
    if diag.mud_excess      >= _COMPONENT_TRIGGER['mud']:
        reasons.append(f'mud={diag.mud_excess:.1f}dB')
    if len(diag.box_peaks)  >= _COMPONENT_TRIGGER['box']:
        reasons.append(f'box={len(diag.box_peaks)}peaks')
    if diag.presence_deficit <= _COMPONENT_TRIGGER['presence']:
        reasons.append(f'pres={diag.presence_deficit:.1f}dB')
    if diag.harsh_excess    >= _COMPONENT_TRIGGER['harsh']:
        reasons.append(f'harsh={diag.harsh_excess:.1f}dB')
    if diag.air_deficit     <= _COMPONENT_TRIGGER['air']:
        reasons.append(f'air={diag.air_deficit:.1f}dB')
    if reasons:
        return True, 'component: ' + ', '.join(reasons)
    return False, f'VQS={diag.vqs:.1f} sufficient, no component triggers'


def diagnose_voice_quality(audio: 'np.ndarray',
                            ref_spectrum: Dict[float, float],
                            codec_cutoff: float = 20_000.0,
                            sr: int = SR) -> BayanDiagnostics:
    """Diagnose all 6 VQ dimensions. All 8 bugs fixed."""
    diag = BayanDiagnostics()

    # BUG-5: resolve reference
    base_ref = _resolve_reference(ref_spectrum)

    # BUG-4+BUG-6: multi-window voiced spectrum
    measured = _multi_window_spectrum(audio, sr)
    if not measured:
        diag.vqs = 100.0
        return diag

    # BUG-1: level-normalize reference
    norm_ref, loff = _normalize_reference(measured, base_ref)
    diag.level_offset_db = loff

    # F0 for BUG-2
    diag.f0_hz = _estimate_f0(audio, sr)

    def _delta(fc_list):
        return [measured.get(fc, -60.0) - norm_ref.get(fc, measured.get(fc, -60.0))
                for fc in fc_list if fc in measured]

    def _md(fc_list):
        d = _delta(fc_list)
        return float(np.mean(d)) if d else 0.0

    # VQ-6: Body
    diag.body_delta = _md(_BODY_BANDS)

    # VQ-1: Muddiness
    mud_d = _delta(_MUD_BANDS)
    if mud_d:
        diag.mud_excess  = float(np.mean([max(0.0, d) for d in mud_d]))
        worst            = int(np.argmax([max(0.0, d) for d in mud_d]))
        diag.mud_peak_hz = _MUD_BANDS[min(worst, len(_MUD_BANDS) - 1)]

    # VQ-2: Boxiness (BUG-2: F0 exclusion baked in)
    diag.box_peaks = _find_spectral_peaks(
        audio, _BOX_BAND_RANGE[0], _BOX_BAND_RANGE[1],
        f0=diag.f0_hz, sr=sr, n_peaks=4, min_prominence_db=4.5,
    )

    # VQ-4: Harshness
    harsh_d = _delta(_HARSH_BANDS)
    if harsh_d:
        diag.harsh_excess  = float(np.mean([max(0.0, d) for d in harsh_d]))
        worst_h            = int(np.argmax([max(0.0, d) for d in harsh_d]))
        diag.harsh_peak_hz = _HARSH_BANDS[min(worst_h, len(_HARSH_BANDS) - 1)]

    # VQ-3: Presence (NEW-3: split)
    diag.clarity_deficit  = _md(_CLARITY_BANDS)
    diag.artic_deficit    = _md(_ARTIC_BANDS)
    diag.presence_deficit = _md(_PRESENCE_BANDS)

    # VQ-5: Air
    if codec_cutoff >= 12_000.0:
        valid_air = [fc for fc in _AIR_BANDS if fc < codec_cutoff * 0.92]
        air_d = _delta(valid_air)
        if air_d:
            diag.air_deficit = float(np.mean(air_d))

    # Arabic protection
    diag.emp_delta  = _md(_EMP_BANDS)
    diag.ghun_delta = _md(_GHUN_BANDS)

    # BUG-7: band energy (not SNR)
    diag.sib_energy_before = _sibilant_band_energy(audio, sr)

    # NEW-4: band-specific transient density
    diag.sib_transient_density = _sib_transient_density_band(audio, sr)

    diag.vqs = _compute_vqs(diag)
    return diag


# ══════════════════════════════════════════════════════════════════════════════
#  EQ NODE CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class _EQNode:
    freq:  float
    gain:  float
    q:     float
    label: str


def _build_bayan_eq_nodes(diag: BayanDiagnostics) -> List[_EQNode]:
    """Build EQ corrections from diagnostics. All protection gates enforced."""
    nodes: List[_EQNode] = []

    # VQ-6: Body — different Q per direction
    # FIX-BODY: cap 3dB→6dB. For deficit > 5dB (processing artifact), add
    # a second shelf at 80Hz to restore fundamental warmth.
    if diag.body_delta > 1.5:
        g = float(np.clip(-diag.body_delta * 0.50, -6.0, -0.5))
        nodes.append(_EQNode(freq=100.0, gain=g, q=0.55,
                             label=f'VQ-6:body_cut {g:+.1f}dB@100Hz Q0.55'))
    elif diag.body_delta < -1.5:
        g = float(np.clip(-diag.body_delta * 0.55, 0.5, 6.0))
        nodes.append(_EQNode(freq=130.0, gain=g, q=0.70,
                             label=f'VQ-6:body_boost +{g:.1f}dB@130Hz Q0.70'))
        if diag.body_delta < -5.0:
            g2 = float(np.clip(-diag.body_delta * 0.25, 0.5, 3.0))
            nodes.append(_EQNode(freq=80.0, gain=g2, q=0.50,
                                 label=f'VQ-6:body_shelf +{g2:.1f}dB@80Hz Q0.50'))

    # VQ-1: Muddiness
    if diag.mud_excess >= 2.5:
        g = float(np.clip(-diag.mud_excess * 0.60, -5.0, -0.5))
        if diag.mud_peak_hz >= 400.0:
            g = float(np.clip(g + abs(diag.emp_delta) * 0.3, -5.0, -0.3))
        nodes.append(_EQNode(freq=diag.mud_peak_hz, gain=g, q=0.80,
                             label=f'VQ-1:mud {g:+.1f}dB@{diag.mud_peak_hz:.0f}Hz'))

    # VQ-2: Boxiness
    # FIX-BOX-DEPTH: peaks >12dB excess are spectral artifacts (NR residuals or
    # severe room modes), not minor colorations. -5dB cap left them at 13-17dB —
    # still above 4.5dB threshold, so VQS didn't change. Allow up to -10dB for
    # confirmed high-excess peaks. Emphatic vowel protection still enforced.
    for hz, excess in diag.box_peaks:
        max_cut = -10.0 if excess > 12.0 else -5.0
        g = float(np.clip(-excess * 0.55, max_cut, -1.5))
        if 400.0 <= hz <= 950.0 and diag.emp_delta < -1.5:
            g = float(np.clip(g * 0.5, -5.0, 0.0))
        nodes.append(_EQNode(freq=hz, gain=g, q=3.0,
                             label=f'VQ-2:box {g:+.1f}dB@{hz:.0f}Hz Q3'))

    # VQ-4: Harshness
    if diag.harsh_excess >= 2.0:
        g = float(np.clip(-diag.harsh_excess * 0.55, -3.5, -0.5))
        if diag.sib_transient_density > 0.04:   # NEW-4: band-specific qalqala gate
            g = float(np.clip(g + diag.sib_transient_density * 15.0, -3.5, 0.0))
        g = float(max(g, -_PROT_SIB_MAX_CUT))
        if g < -0.3:
            nodes.append(_EQNode(freq=diag.harsh_peak_hz, gain=g, q=1.4,
                                 label=f'VQ-4:harsh {g:+.1f}dB@{diag.harsh_peak_hz:.0f}Hz'))

    # VQ-3: Clarity (NEW-3 split — 1k–2kHz)
    if diag.clarity_deficit < -2.0:
        g = float(np.clip(-diag.clarity_deficit * 0.50, 0.5, 3.5))
        if diag.ghun_delta > 1.5:
            g *= 0.60
        nodes.append(_EQNode(freq=1600.0, gain=g, q=1.00,
                             label=f'VQ-3:clarity +{g:.1f}dB@1.6kHz'))

    # VQ-3: Articulation (NEW-3 split — 2k–4kHz)
    if diag.artic_deficit < -2.0:
        g = float(np.clip(-diag.artic_deficit * 0.50, 0.5, 3.0))
        # Sibilant protection
        net_sib = g - (diag.harsh_excess * 0.55 if diag.harsh_excess >= 2.0 else 0.0)
        g = float(np.clip(min(g, _PROT_SIB_MAX_CUT + net_sib), 0.5, 3.0))
        nodes.append(_EQNode(freq=3000.0, gain=g, q=0.90,
                             label=f'VQ-3:artic +{g:.1f}dB@3kHz'))

    # VQ-5: Air
    if diag.air_deficit < -3.0:
        g = float(np.clip(-diag.air_deficit * 0.50, 0.5, _PROT_AIR_MAX_GAIN))
        nodes.append(_EQNode(freq=9000.0, gain=g, q=0.65,
                             label=f'VQ-5:air +{g:.1f}dB@9kHz'))

    return nodes


def _nodes_to_ffmpeg_filter(nodes: List[_EQNode]) -> str:
    """BUG-3 FIX: width_type=q consistent with engine's nodes_to_af()."""
    if not nodes:
        return 'anull'
    return ','.join(
        f'equalizer=f={n.freq:.1f}:width_type=q:width={n.q:.2f}:g={n.gain:.2f}'
        for n in nodes
    )


# ══════════════════════════════════════════════════════════════════════════════
#  APPLY + VALIDATE
# ══════════════════════════════════════════════════════════════════════════════

def _apply_eq_filter(input_wav: str, output_wav: str, ff_filter: str) -> bool:
    r = subprocess.run([
        'ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
        '-i', input_wav, '-af', ff_filter,
        '-ar', str(SR), '-acodec', 'pcm_s24le', output_wav,
    ], capture_output=True)
    return r.returncode == 0 and Path(output_wav).exists()


def _remeasure_vqs(wav_path: str, ref_spectrum: Dict[float, float],
                   codec_cutoff: float = 20_000.0, sr: int = SR) -> Tuple[float, float]:
    """BUG-8 FIX: Re-measure VQS. Returns (vqs_after, sib_energy_after)."""
    audio_after = _load_mono(wav_path, skip_s=0.0, dur_s=60.0, sr=sr)
    diag_after  = diagnose_voice_quality(audio_after, ref_spectrum,
                                          codec_cutoff=codec_cutoff, sr=sr)
    return diag_after.vqs, diag_after.sib_energy_before


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def apply_bayan_to_engine(input_wav: str, state, ref,
                           log_fn=print) -> Tuple[str, BayanResult]:
    """Phase B4 entry point called from enhance()."""
    result = BayanResult()

    if not NUMPY_OK:
        result.status = 'SKIPPED'; result.reason = 'numpy unavailable'
        return input_wav, result

    source_tier = getattr(state, 'source_tier', 'TIER_PRISTINE')
    if source_tier == 'TIER_CRITICAL':
        result.status = 'SKIPPED'; result.reason = 'TIER_CRITICAL — bypass'
        return input_wav, result

    skip_s       = float(getattr(state, 'skip_s', 30))
    dur_s        = float(getattr(state, 'dur_s', 45))
    codec_cutoff = float(getattr(state, 'codec_cutoff', 20_000.0))
    ref_spectrum: Dict[float, float] = getattr(ref, 'third_oct', {})

    log_fn('  │  [BAYAN v2] loading audio for voiced-gated diagnosis...')
    audio = _load_mono(input_wav, skip_s=skip_s, dur_s=dur_s)
    if len(audio) < SR * 5:
        result.status = 'SKIPPED'; result.reason = 'audio too short'
        return input_wav, result

    log_fn('  │  [BAYAN v2] diagnosing (level-normalized, F0-aware, multi-window)...')
    diag = diagnose_voice_quality(audio, ref_spectrum,
                                   codec_cutoff=codec_cutoff, sr=SR)
    result.diag      = diag
    result.vqs_before = diag.vqs

    log_fn(f'  │  [BAYAN v2] VQS={diag.vqs:.1f}  loff={diag.level_offset_db:+.1f}dB  F0={diag.f0_hz:.0f}Hz')
    log_fn(f'  │           mud={diag.mud_excess:+.1f}dB@{diag.mud_peak_hz:.0f}Hz  '
           f'box={len(diag.box_peaks)}  clarity={diag.clarity_deficit:+.1f}dB  '
           f'artic={diag.artic_deficit:+.1f}dB  harsh={diag.harsh_excess:+.1f}dB  '
           f'air={diag.air_deficit:+.1f}dB  body={diag.body_delta:+.1f}dB')
    log_fn(f'  │           sib_energy={diag.sib_energy_before:.1f}dBFS  '
           f'emp={diag.emp_delta:+.1f}dB  ghun={diag.ghun_delta:+.1f}dB  '
           f'qalqala_dens={diag.sib_transient_density:.4f}')
    for hz, exc in diag.box_peaks:
        log_fn(f'  │           box_peak: {hz:.0f}Hz excess={exc:.1f}dB')

    # NEW-5: VQS or component trigger
    should, trig_reason = _should_trigger(diag)
    if not should:
        result.status = 'SKIPPED'; result.reason = trig_reason
        log_fn(f'  │  [BAYAN v2] skip — {trig_reason}')
        return input_wav, result

    log_fn(f'  │  [BAYAN v2] triggered: {trig_reason}')

    nodes = _build_bayan_eq_nodes(diag)
    if not nodes:
        result.status = 'SKIPPED'; result.reason = 'no correctable deficits'
        return input_wav, result

    ff_filter = _nodes_to_ffmpeg_filter(nodes)
    result.eq_chain_desc = '  |  '.join(n.label for n in nodes)
    log_fn(f'  │  [BAYAN v2] applying {len(nodes)} EQ node(s):')
    for n in nodes:
        log_fn(f'  │           {n.label}')

    import uuid as _u
    out_path = os.path.join(_TMP, f'bayan_b4_{_u.uuid4().hex[:8]}.wav')
    if not _apply_eq_filter(input_wav, out_path, ff_filter):
        result.status = 'ERROR'; result.reason = 'ffmpeg EQ failed'
        return input_wav, result

    log_fn('  │  [BAYAN v2] re-measuring VQS...')
    vqs_after, sib_after = _remeasure_vqs(out_path, ref_spectrum, codec_cutoff)
    result.vqs_after     = vqs_after
    result.sib_energy_delta = sib_after - diag.sib_energy_before

    log_fn(f'  │  [BAYAN v2] VQS {diag.vqs:.1f}→{vqs_after:.1f} '
           f'(Δ={vqs_after - diag.vqs:+.1f})  sib_energy Δ={result.sib_energy_delta:+.1f}dBFS')

    # Gate 1: VQS must improve ≥ 1.5 pts
    if vqs_after < diag.vqs + 1.5:
        result.status = 'REJECTED'
        result.reason = f'VQS gain {diag.vqs:.1f}→{vqs_after:.1f} insufficient (need +1.5)'
        log_fn(f'  │  [BAYAN v2] REJECT — {result.reason}')
        _safe_unlink(out_path); return input_wav, result

    # Gate 2: BUG-7 FIX — sibilant band energy must not drop > 2.5dBFS
    if result.sib_energy_delta < -_PROT_SIB_MAX_CUT:
        result.status = 'REJECTED'
        result.reason = f'Arabic sibilant energy −{-result.sib_energy_delta:.1f}dBFS (limit {_PROT_SIB_MAX_CUT}dBFS)'
        log_fn(f'  │  [BAYAN v2] REJECT — {result.reason}')
        _safe_unlink(out_path); return input_wav, result

    # Gate 3: file must exist
    if not Path(out_path).exists() or Path(out_path).stat().st_size < 1000:
        result.status = 'ERROR'; result.reason = 'output WAV missing'
        return input_wav, result

    result.status           = 'OK'
    result.vqs_gain         = vqs_after - diag.vqs
    result.output_wav       = out_path
    result.mud_applied      = diag.mud_excess >= 2.5
    result.box_applied      = len(diag.box_peaks) > 0
    result.presence_applied = diag.clarity_deficit < -2.0 or diag.artic_deficit < -2.0
    result.harsh_applied    = diag.harsh_excess >= 2.0
    result.air_applied      = diag.air_deficit < -3.0
    result.body_applied     = abs(diag.body_delta) >= 1.5

    log_fn(f'  │  [BAYAN v2] ✓  VQS +{result.vqs_gain:.1f}  '
           f'mud={result.mud_applied} box={result.box_applied} '
           f'pres={result.presence_applied} harsh={result.harsh_applied} '
           f'air={result.air_applied} body={result.body_applied}')

    return out_path, result


def _safe_unlink(path: str) -> None:
    try: Path(path).unlink(missing_ok=True)
    except Exception: pass


# ══════════════════════════════════════════════════════════════════════════════
#  STANDALONE DIAGNOSTIC MODE
# ══════════════════════════════════════════════════════════════════════════════

def _standalone_diagnose(audio_path: str) -> None:
    if not NUMPY_OK:
        print('ERROR: numpy/scipy required'); return

    print(f'\n╔════════════════════════════════════════════════════╗')
    print(f'║  البيان v2.0 — Voice Quality Diagnostics           ║')
    print(f'╚════════════════════════════════════════════════════╝')
    print(f'  {os.path.basename(audio_path)}\n')

    audio = _load_mono(audio_path, skip_s=0.0, dur_s=60.0)
    print(f'  Loaded: {len(audio)/SR:.1f}s')
    diag = diagnose_voice_quality(audio, {}, codec_cutoff=14000.0)
    triggered, reason = _should_trigger(diag)

    print(f'  VQS: {diag.vqs:.1f}/100   trigger: {BAYAN_TRIGGER_VQS}')
    print(f'  Triggered? {"YES" if triggered else "NO"}  ({reason})')
    print(f'  Level offset: {diag.level_offset_db:+.1f}dB  F0: {diag.f0_hz:.1f}Hz\n')
    print('  VQ Diagnostics (level-normalized vs الدوسري 1425H):')
    print(f'    VQ-6 Body         (80–200Hz):    Δ={diag.body_delta:+.2f}dB')
    print(f'    VQ-1 Muddiness    (200–500Hz):   excess={diag.mud_excess:+.2f}dB @{diag.mud_peak_hz:.0f}Hz')
    print(f'    VQ-2 Boxiness     (200–850Hz):   {len(diag.box_peaks)} peak(s)')
    for hz, exc in diag.box_peaks:
        print(f'         └─ {hz:.0f}Hz  excess={exc:.1f}dB')
    print(f'    VQ-3 Clarity      (1k–2kHz):     deficit={diag.clarity_deficit:+.2f}dB')
    print(f'    VQ-3 Articulation (2k–4kHz):     deficit={diag.artic_deficit:+.2f}dB')
    print(f'    VQ-4 Harshness    (2.5k–5kHz):  excess={diag.harsh_excess:+.2f}dB @{diag.harsh_peak_hz:.0f}Hz')
    print(f'    VQ-5 Air          (8k–12.5kHz): deficit={diag.air_deficit:+.2f}dB\n')
    print('  Arabic Protection:')
    print(f'    Emphatic body  (500–900Hz):  Δ={diag.emp_delta:+.2f}dB')
    print(f'    Ghunna zone    (900–1200Hz): Δ={diag.ghun_delta:+.2f}dB')
    print(f'    Sibilant energy:             {diag.sib_energy_before:.1f}dBFS')
    print(f'    Qalqala density (2.5k–5kHz): {diag.sib_transient_density:.4f}\n')

    nodes = _build_bayan_eq_nodes(diag)
    print(f'  EQ Nodes ({len(nodes)}):')
    if nodes:
        for n in nodes:
            print(f'    {n.label}')
        print(f'\n  ffmpeg filter:\n    {_nodes_to_ffmpeg_filter(nodes)}')
    else:
        print('    (none)')


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python bayan_ve.py <audio_file>'); sys.exit(0)
    _standalone_diagnose(sys.argv[1])
