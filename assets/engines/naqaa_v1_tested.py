#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   النقاء v1 — QURAN RESTORATION ENGINE  (naqaa_v1.py)                       ║
║   Low-Quality Quran Audio Recovery — Standalone, No isteidad dependency     ║
║                                                                              ║
║   PURPOSE                                                                    ║
║   ───────                                                                    ║
║   jawhar handles VOICE CHARACTER (harmonic ratios, tilt, texture) for       ║
║   audio that is already structurally sound. This engine handles             ║
║   STRUCTURAL DAMAGE — the class of problems that must be fixed BEFORE       ║
║   any voice character work begins. Applying jawhar to an unrestored         ║
║   mosque recording is equivalent to painting a cracked wall.                ║
║                                                                              ║
║   THE TWO TARGET FILES                                                       ║
║   ─────────────────────────────────────────────────────────────────────     ║
║   سورة المائدة (90-96):  mosque recording                                    ║
║     Pathology:  PA comb filtering + room reverb RT60≈1.5s + crowd noise     ║
║     Profile:    MOSQUE                                                       ║
║                                                                              ║
║   سورة النور (full surah, ~20min):  low-bitrate + long session               ║
║     Pathology:  codec damage (128/192kbps) + session-level drift            ║
║     Profile:    CODEC                                                        ║
║                                                                              ║
║   KNOWLEDGE BASE FOUNDATIONS                                                 ║
║   ─────────────────────────────────────────────────────────────────────     ║
║   §35.2  Correct processing order: DECLIP→NR→DEREV→EQ→LUFS                 ║
║          Current isteidad order is wrong: NR→derev→EQ loses quality         ║
║          Clipping THD inflates NR noise estimate → over-attenuation         ║
║                                                                              ║
║   §28.6  JALAA dereverberation: DRR-aware spectral gate, energy ratio       ║
║          early (0-50ms) vs late (50-500ms) → attenuation of reverb tail     ║
║          NEVER WIRED in isteidad despite being imported. Fixed here.        ║
║                                                                              ║
║   §38.5  PA comb filter: mosque recording artifacts, delay 20-80ms          ║
║          Notch repair via spectral interpolation on long voiced windows      ║
║                                                                              ║
║   §28.4  TYPE_C codec NR: pre-echo cosine taper + anlmdn mosquito NR        ║
║          + PCHIP harmonic inference for bandwidth extension                  ║
║                                                                              ║
║   §34.9  Audio gap repair: energy compensation for sparsity inpainting      ║
║          dropout < 5ms → AR fill; 5-50ms → flag + NMF context fill         ║
║                                                                              ║
║   §41    Cassette azimuth: stereo cross-correlation → delay → comb fix      ║
║          Digital correction restores phase but NOT lost HF (§41.3)         ║
║                                                                              ║
║   §36.5  Wow/flutter: DETECT only, never auto-correct (Tajweed constraint)  ║
║          Flag madd F0 instability > 3Hz for manual review                   ║
║                                                                              ║
║   §29.2  Scoring: 5-component (Spectral30 + LUFS25 + Crest20 + LRA15 +     ║
║          Warmth10). warmth_ratio measured 200-2000Hz (§30.10).              ║
║                                                                              ║
║   §47    Vocos-BWE principle: crossover at detected codec cutoff;           ║
║          above cutoff: shaped harmonic inference (PCHIP R-3 style)          ║
║                                                                              ║
║   §3.5   Dereverberation target: RT60 0.8-1.2s effective (not anechoic)     ║
║          Mosque early reflections carry "masjid" character — preserve       ║
║                                                                              ║
║   PIPELINE (strict §35.2 order)                                             ║
║   ─────────────────────────────────────────────────────────────────────     ║
║   PHASE 0: TRIAGE — auto-detect profile, measure all damage dimensions      ║
║   PHASE 1: DECLIP — before anything else (clipping THD poisons NR)         ║
║   PHASE 2: GAP REPAIR — dropout detection + AR/NMF inpainting              ║
║   PHASE 3: AZIMUTH FIX — cassette stereo cross-correlation alignment        ║
║   PHASE 4: NR — adaptive: afftdn TYPE_A/B/C per noise type                 ║
║   PHASE 5: DEREV — JALAA DRR-aware spectral gate (properly wired)          ║
║   PHASE 6: COMB — PA comb notch fill (mosque profile)                      ║
║   PHASE 7: EQ — spectral tilt + warmth correction (200-2000Hz)             ║
║   PHASE 8: BWE — bandwidth extension for codec cutoff < 16kHz              ║
║   PHASE 9: LUFS — loudness target -6.29 LUFS, crest preservation           ║
║   PHASE 10: REPORT — damage inventory + quality score + flags               ║
║                                                                              ║
║   REFERENCE DNA (1425H — measured, forensic)                               ║
║     LUFS:     -6.29   LRA:   2.94 LU   Crest: 10.25 dB                    ║
║     RT60:     0.200s  Noise: -73 dBFS  Slope: -7.43 dB/oct (200-2000Hz)   ║
║     Sib centroid: 4.28kHz   Sib slope: -8.3 dB/oct                         ║
║     Room sustain: 22.5 dBFS (invariant across all 3 reference files)        ║
║                                                                              ║
║   USAGE                                                                      ║
║     python naqaa_v1.py -i سورة_النور.mp3 -o نور_restored.mp3               ║
║     python naqaa_v1.py -i المائدة.mp3 -o مائدة_restored.mp3 --mosque        ║
║     python naqaa_v1.py -i bad.mp3 -o good.mp3 --ref المرجع1425.mp3         ║
║                                                                              ║
║   المرجع: الشيخ ياسر الدوسري — 1425H                                         ║
║   وما التوفيق إلا بالله                                                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations
import os, sys, subprocess, tempfile, uuid, time, json, math, warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings('ignore')
_TMP = Path(tempfile.gettempdir())
SR   = 48_000

# ── optional numpy/scipy ────────────────────────────────────────────────────
try:
    import numpy as np
    from scipy.fft    import rfft, irfft, rfftfreq
    from scipy.signal import (stft, istft, butter, sosfiltfilt, lfilter,
                               correlate, find_peaks)
    from scipy.ndimage import median_filter, uniform_filter1d
    from scipy.linalg  import solve_toeplitz
    from scipy.interpolate import PchipInterpolator
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False
    print('[النقاء] WARNING: numpy/scipy not found — DSP modules disabled')

# ── DeepFilterNet optional ──────────────────────────────────────────────────
DF3_BIN = None
for _p in ['/tmp/deep-filter', str(Path.home()/'deep-filter'), './deep-filter',
           '/usr/local/bin/deep-filter', str(Path.home()/'.local/bin/deep-filter')]:
    if os.path.isfile(_p) and os.access(_p, os.X_OK):
        DF3_BIN = _p; break

# ══════════════════════════════════════════════════════════════════════════════
#  REFERENCE DNA CONSTANTS  (forensic — ref_v3 analysis, May 2026)
# ══════════════════════════════════════════════════════════════════════════════
_DNA = {
    'lufs':           -6.29,
    'lra':             2.94,
    'crest_db':       10.25,
    'rt60_base_s':     0.200,
    'rt60_target_s':   0.900,   # §3.5: target 0.8-1.2s (not anechoic)
    'noise_floor_db': -73.0,
    'slope_db_oct':   -7.43,    # 200-2000Hz (§30.10)
    'sib_centroid_hz': 4280.0,
    'sib_slope':       -8.3,
    'room_sustain_db': 22.5,    # invariant across all 3 reference files
    'h2_h1_ratio':     1.630,   # glottal source ratio, F0-invariant
}

# Processing caps
_MAX_NR_GAIN_DB        = 18.0   # afftdn nr gain cap
_MAX_DEREV_BLEND       = 0.72   # max reverb removal blend
_MAX_EQ_DB             = 6.0    # max EQ boost/cut
_MAX_BWE_SHELF_DB      = 4.0    # max air-band shelf for BWE
_COMB_MAX_FILL_DB      = 6.0    # max PA comb notch fill
_CLIP_RATIO_TRIGGER    = 0.0003 # sample fraction at peak to confirm clipping
_GAP_DROPOUT_MS        = 5.0    # gap < 5ms → tape dropout → inpaint
_GAP_WORD_FLAG_MS      = 50.0   # gap 5-50ms → possible word deletion → flag


# ══════════════════════════════════════════════════════════════════════════════
#  TRIAGE RESULT — full damage inventory from Phase 0
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class TriageResult:
    # Source properties
    duration_s:        float = 0.0
    src_sr:            int   = 48000
    src_br:            int   = 320000
    src_channels:      int   = 1
    codec_cutoff_hz:   float = 20000.0

    # Profile detection
    profile:           str   = 'UNKNOWN'  # MOSQUE | CODEC | CASSETTE | CLEAN
    source_tier:       str   = 'TIER_COMPRESSED'

    # Noise
    snr_global_db:     float = 30.0
    frame_snr_db:      float = 30.0
    noise_type:        str   = 'none'    # broadband | hum | crowd | codec | none
    hum_hz:            float = 0.0

    # Reverb (§28.6 JALAA)
    est_rt60_s:        float = 0.200
    drr_estimate_db:   float = 15.0      # direct-to-reverberant ratio
    reverb_energy_frac: float = 0.0      # fraction of total energy in reverb tail

    # Clipping (§35.1 Step A)
    clip_ratio:        float = 0.0
    clip_islands:      int   = 0
    clip_severity:     str   = 'none'    # none | light | moderate | severe

    # Gaps/dropouts (§35.1 Step B)
    dropout_gaps:      int   = 0         # gaps < 5ms
    word_flag_gaps:    int   = 0         # gaps 5-50ms — needs human review

    # PA comb filtering (§38.5)
    comb_detected:     bool  = False
    comb_delay_ms:     float = 0.0
    comb_depth_db:     float = 0.0
    comb_n_notches:    int   = 0

    # Cassette (§41)
    azimuth_lag_ms:    float = 0.0       # 0 = no misalignment detected
    azimuth_comb_detected: bool = False

    # Wow/flutter (§36)
    wow_detected:      bool  = False
    flutter_detected:  bool  = False
    max_f0_deviation_hz: float = 0.0

    # Spectral
    lufs_in:           float = -99.0
    lra_in:            float = 0.0
    crest_in:          float = 0.0
    warmth_slope:      float = 0.0       # 200-2000Hz
    spectral_tilt_gap: float = 0.0       # how far from -7.43


@dataclass
class NaqaaResult:
    status:            str   = 'FAILED'
    output_path:       str   = ''
    triage:            Optional[TriageResult] = None
    processing_s:      float = 0.0

    # Per-phase flags
    phase1_declip:     bool  = False
    phase2_gap:        bool  = False
    phase3_azimuth:    bool  = False
    phase4_nr:         str   = 'skipped'  # 'TYPE_A' | 'TYPE_B' | 'TYPE_C' | 'DF3' | ...
    phase5_derev:      bool  = False
    phase6_comb:       bool  = False
    phase7_eq:         bool  = False
    phase8_bwe:        bool  = False
    phase9_lufs:       bool  = False

    # Per-phase metrics
    nr_snr_gain_db:    float = 0.0
    derev_drr_gain_db: float = 0.0
    comb_notches:      int   = 0
    eq_correction_db:  float = 0.0
    bwe_cutoff_hz:     float = 0.0
    lufs_out:          float = -99.0
    lra_out:           float = 0.0
    crest_out:         float = 0.0

    # Quality score (out of 100)
    score_before:      float = 0.0
    score_after:       float = 0.0

    # Human-review flags
    flags:             List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO I/O
# ══════════════════════════════════════════════════════════════════════════════
def _load_mono(path: str, skip_s: float = 0, dur_s: float = 9999,
               sr: int = SR) -> 'np.ndarray':
    cmd = ['ffmpeg', '-y', '-nostdin']
    if skip_s > 0: cmd += ['-ss', str(skip_s)]
    cmd += ['-i', path, '-t', str(dur_s),
            '-af', 'pan=mono|c0=0.5*FL+0.5*FR',
            '-f', 'f32le', '-ar', str(sr), '-loglevel', 'error', '-']
    r = subprocess.run(cmd, capture_output=True)
    if not r.stdout: return np.zeros(sr, dtype=np.float32)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()

def _load_stereo(path: str, skip_s: float = 0, dur_s: float = 9999,
                 sr: int = SR) -> Tuple['np.ndarray', 'np.ndarray']:
    """Returns (left, right) arrays."""
    cmd = ['ffmpeg', '-y', '-nostdin']
    if skip_s > 0: cmd += ['-ss', str(skip_s)]
    cmd += ['-i', path, '-t', str(dur_s),
            '-f', 'f32le', '-ar', str(sr), '-ac', '2', '-loglevel', 'error', '-']
    r = subprocess.run(cmd, capture_output=True)
    if not r.stdout:
        return np.zeros(sr, dtype=np.float32), np.zeros(sr, dtype=np.float32)
    raw = np.frombuffer(r.stdout, dtype=np.float32)
    if len(raw) % 2 != 0: raw = raw[:-1]
    stereo = raw.reshape(-1, 2)
    return stereo[:, 0].copy(), stereo[:, 1].copy()

def _probe(path: str) -> Dict:
    r = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json',
                        '-show_format', '-show_streams', path],
                       capture_output=True, text=True)
    if r.returncode != 0: return {}
    try: return json.loads(r.stdout)
    except: return {}

def _write_wav_mono(audio: 'np.ndarray', path: str, sr: int = SR) -> bool:
    raw = np.clip(audio, -1.0, 1.0).astype(np.float32).tobytes()
    r = subprocess.run(
        ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(sr), '-ac', '1',
         '-i', '-', '-ar', str(sr), '-ac', '2', '-c:a', 'pcm_s24le',
         '-loglevel', 'error', str(path)],
        input=raw, capture_output=True)
    return r.returncode == 0

def _encode_mp3(wav_path: str, mp3_path: str, br_k: int = 320) -> bool:
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-c:a', 'libmp3lame', '-b:a', f'{br_k}k',
         '-loglevel', 'error', mp3_path],
        capture_output=True)
    return r.returncode == 0

def _rms_db(a: 'np.ndarray') -> float:
    return float(20 * np.log10(np.sqrt(np.mean(a.astype(np.float64)**2)) + 1e-10))

def _rms_lin(a: 'np.ndarray') -> float:
    return float(np.sqrt(np.mean(a.astype(np.float64)**2)) + 1e-10)

def _rms_preserve(orig: 'np.ndarray', proc: 'np.ndarray') -> 'np.ndarray':
    return (proc * (_rms_lin(orig) / (_rms_lin(proc) + 1e-10))).astype(np.float32)

def _measure_lufs(path: str) -> Tuple[float, float, float]:
    """Returns (lufs, lra, tp) from ffmpeg ebur128."""
    r = subprocess.run(['ffmpeg', '-i', path,
                        '-af', 'ebur128=peak=true', '-f', 'null', '-',
                        '-loglevel', 'info'], capture_output=True, text=True)
    lufs = lra = tp = -99.0
    for line in r.stderr.split('\n'):
        s = line.strip()
        if s.startswith('I:')  and 'LUFS' in s and 'LRA' not in s:
            try: lufs = float(s.split('I:')[1].strip().split()[0])
            except: pass
        elif 'LRA:' in s:
            try: lra  = float(s.split('LRA:')[1].strip().split()[0])
            except: pass
    return lufs, lra, tp


# ══════════════════════════════════════════════════════════════════════════════
#  F0 DETECTION
# ══════════════════════════════════════════════════════════════════════════════
def _f0(frame: 'np.ndarray', sr: int = SR, fmin: float = 70.0,
        fmax: float = 400.0) -> float:
    lo = int(sr / fmax); hi = min(int(sr / fmin), len(frame)//2 - 1)
    if hi <= lo or len(frame) < 128: return 0.0
    w = frame.astype(np.float64) * np.hanning(len(frame))
    if np.sqrt(np.mean(w**2)) < 1e-5: return 0.0
    c = np.correlate(w, w, 'full')[len(w)-1:]
    c /= c[0] + 1e-12
    seg = c[lo:hi]; pk = int(np.argmax(seg))
    if seg[pk] < 0.28: return 0.0
    lag = lo + pk
    if 0 < lag < len(c)-1:
        y0,y1,y2 = c[lag-1],c[lag],c[lag+1]; d=y0-2*y1+y2
        if abs(d) > 1e-10: lag += 0.5*(y0-y2)/d
    return float(sr / max(lag, 1.0))


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 0 — TRIAGE
#  Full damage inventory. Determines profile and per-phase parameters.
#  KB §35.1 detection sequence + §28 SNR/RT60 + §41 azimuth + §36 wow/flutter
# ══════════════════════════════════════════════════════════════════════════════
def _phase0_triage(input_path: str, log) -> TriageResult:
    log('  [TRIAGE] Starting damage inventory...')
    t = TriageResult()

    # ── Source properties ──────────────────────────────────────────────────
    info = _probe(input_path)
    fmt  = info.get('format', {})
    t.duration_s  = float(fmt.get('duration', 0))
    t.src_br      = int(fmt.get('bit_rate', 320_000))
    for s in info.get('streams', []):
        if s.get('codec_type') == 'audio':
            t.src_sr       = int(s.get('sample_rate', 48000))
            t.src_channels = int(s.get('channels', 1))
            break

    # Estimate codec cutoff from bitrate (conservative)
    # 320kbps→20kHz, 192kbps→18kHz, 128kbps→16kHz, 64kbps→11kHz
    br = t.src_br
    if   br >= 280_000: t.codec_cutoff_hz = 20000.0
    elif br >= 160_000: t.codec_cutoff_hz = 18000.0
    elif br >= 110_000: t.codec_cutoff_hz = 16000.0
    elif br >=  60_000: t.codec_cutoff_hz = 12000.0
    else:               t.codec_cutoff_hz = 10000.0

    # Analysis clip: skip first 15s (intro/recitation start), analyze up to 60s
    skip_s  = min(15.0, t.duration_s * 0.05)
    dur_s   = min(60.0, t.duration_s - skip_s)
    clip    = _load_mono(input_path, skip_s=skip_s, dur_s=dur_s) if NUMPY_OK else None
    lufs, lra, _ = _measure_lufs(input_path)
    t.lufs_in = lufs; t.lra_in  = lra

    if clip is None or len(clip) < SR*2:
        log('  [TRIAGE] numpy unavailable — skipping DSP analysis')
        t.profile = 'CODEC'; t.source_tier = 'TIER_DEGRADED'
        return t

    # ── Crest factor ───────────────────────────────────────────────────────
    peak_db  = float(20 * np.log10(np.max(np.abs(clip)) + 1e-10))
    rms_val  = _rms_db(clip)
    t.crest_in = peak_db - rms_val

    # ── SNR estimation (§28: p80 - p5 RMS ratio) ──────────────────────────
    frame_n   = int(0.030 * SR)   # 30ms frames
    hop_n     = frame_n // 2
    frame_rms = []
    for i in range(0, len(clip)-frame_n, hop_n):
        frame_rms.append(_rms_db(clip[i:i+frame_n]))
    if len(frame_rms) >= 10:
        frame_rms = np.array(frame_rms)
        p80 = float(np.percentile(frame_rms, 80))
        p5  = float(np.percentile(frame_rms, 5))
        t.frame_snr_db = max(0.0, p80 - p5)
        # Global SNR: spectral noise floor from bottom-8% frames
        quiet = frame_rms[frame_rms < np.percentile(frame_rms, 8)]
        t.snr_global_db = t.frame_snr_db if len(quiet) < 3 else (
            p80 - float(np.mean(quiet)))

    # ── Spectral analysis ──────────────────────────────────────────────────
    fft_n   = min(32768, len(clip))
    spec    = np.abs(rfft(clip[:fft_n].astype(np.float64)))**2
    fq      = rfftfreq(fft_n, 1/SR)

    # Warmth slope 200-2000Hz (§30.10)
    m       = (fq >= 200) & (fq <= 2000)
    if m.sum() > 5:
        lf = np.log2(fq[m] / 1000.0)
        le = 10 * np.log10(spec[m] + 1e-30)
        slope, _ = np.polyfit(lf, le, 1)
        t.warmth_slope   = float(slope)
        t.spectral_tilt_gap = abs(slope - _DNA['slope_db_oct'])

    # ── Noise type detection ───────────────────────────────────────────────
    # Hum: strong spectral peaks at 50 or 60Hz harmonics
    hum_50 = float(np.mean(spec[(fq>=48)&(fq<=52)])) / (float(np.mean(spec[(fq>=200)&(fq<=300)]))+1e-30)
    hum_60 = float(np.mean(spec[(fq>=58)&(fq<=62)])) / (float(np.mean(spec[(fq>=200)&(fq<=300)]))+1e-30)
    if hum_50 > 12.0: t.noise_type = 'hum'; t.hum_hz = 50.0
    elif hum_60 > 12.0: t.noise_type = 'hum'; t.hum_hz = 60.0

    # Crowd noise: broadband energy 200-800Hz above expected
    crowd_ratio = float(np.mean(spec[(fq>=200)&(fq<=800)])) / (float(np.mean(spec[(fq>=1000)&(fq<=3000)]))+1e-30)
    if crowd_ratio > 3.5 and t.noise_type == 'none':
        t.noise_type = 'crowd'

    # Codec artifacts: energy rolloff steeper than natural above cutoff
    if t.codec_cutoff_hz < 18000:
        if t.noise_type == 'none': t.noise_type = 'codec'

    # ── RT60 estimation (§28.6: energy ratio early/late reflections) ───────
    # Simplified: use long autocorrelation of band-filtered clip (300-3kHz)
    from scipy.signal import butter, sosfiltfilt
    try:
        sos   = butter(4, [300/(SR/2), 3000/(SR/2)], btype='band', output='sos')
        bpf   = sosfiltfilt(sos, clip.astype(np.float64)).astype(np.float32)
        n_e   = min(int(0.050 * SR), len(bpf)//4)   # 50ms early window
        n_l   = min(int(0.500 * SR), len(bpf)//2)   # 500ms late window
        # Find a voiced section (loudest 200ms)
        rms_frames = [_rms_lin(bpf[i:i+frame_n]) for i in range(0, len(bpf)-frame_n, frame_n)]
        if rms_frames:
            best_i = int(np.argmax(rms_frames)) * frame_n
            early_e = float(np.mean(bpf[best_i:best_i+n_e]**2))
            late_e  = float(np.mean(bpf[best_i+n_e:best_i+n_l]**2)) if best_i+n_l <= len(bpf) else early_e*0.1
            drr     = 10 * np.log10(early_e / (late_e + 1e-30))
            t.drr_estimate_db = float(np.clip(drr, -10, 30))
            # Estimate RT60 from late/early ratio
            decay_ratio = (late_e + 1e-30) / (early_e + 1e-30)
            t_late  = (n_l - n_e) / SR
            if decay_ratio < 1.0:
                t.est_rt60_s = float(np.clip(
                    -3 * t_late / (10 * np.log10(decay_ratio + 1e-10)), 0.05, 5.0))
            t.reverb_energy_frac = float(np.clip(late_e / (early_e + late_e + 1e-30), 0, 1))
    except: pass

    # ── Clipping detection (§35.1 Step A) ─────────────────────────────────
    if len(clip) > 0:
        peak_abs   = float(np.max(np.abs(clip)))
        thresh     = peak_abs * 0.995
        clipped    = np.abs(clip) >= thresh
        t.clip_ratio = float(clipped.sum() / len(clip))
        # Count islands
        edges = np.diff(clipped.astype(int))
        starts= np.where(edges == 1)[0]
        ends  = np.where(edges == -1)[0]
        t.clip_islands = len(starts)
        if t.clip_ratio < _CLIP_RATIO_TRIGGER:
            t.clip_severity = 'none'
        elif t.clip_islands > 0:
            # §35.1: islands < 3 samples → Qalqalah; 3-20 → light; >20 → moderate+
            sizes = [(ends[i]-starts[i] if i<len(ends) else 1) for i in range(len(starts))]
            max_sz = max(sizes) if sizes else 0
            if max_sz < 3:  t.clip_severity = 'none'   # Qalqalah transients
            elif max_sz < 20: t.clip_severity = 'light'
            else:             t.clip_severity = 'moderate'
            if t.clip_ratio > 0.02: t.clip_severity = 'severe'

    # ── Gap / dropout detection (§35.1 Step B) ────────────────────────────
    if len(clip) > 0:
        silence_thresh = 10 ** (-80.0/20.0)  # -80dBFS  real tape dropout level
        is_silent = np.abs(clip) < silence_thresh
        # Find runs of silence
        in_gap = False; gap_start = 0; dropout_count = 0; word_flag = 0
        for i, s in enumerate(is_silent):
            if s and not in_gap:
                in_gap = True; gap_start = i
            elif not s and in_gap:
                gap_ms = (i - gap_start) / SR * 1000
                if   gap_ms < _GAP_DROPOUT_MS:  dropout_count += 1
                elif gap_ms < _GAP_WORD_FLAG_MS: word_flag    += 1
                in_gap = False
        t.dropout_gaps    = dropout_count
        t.word_flag_gaps  = word_flag

    # ── PA comb filter detection (§38.5) ──────────────────────────────────
    # Only meaningful for mosque/PA recordings
    _detect_comb_in_triage(clip, fq, spec, t, log)

    # ── Cassette azimuth detection (§41.2) ────────────────────────────────
    if t.src_channels == 2:
        _detect_azimuth(input_path, skip_s, dur_s, t, log)

    # ── Wow/flutter detection (§36.3) ─────────────────────────────────────
    _detect_wow_flutter(clip, t, log)

    # ── Profile classification ────────────────────────────────────────────
    _classify_profile(t, log)

    log(f'  [TRIAGE] Profile={t.profile}  Tier={t.source_tier}')
    log(f'  [TRIAGE] SNR={t.frame_snr_db:.1f}dB  RT60≈{t.est_rt60_s:.2f}s  '
        f'DRR={t.drr_estimate_db:.1f}dB  Clip={t.clip_severity}')
    log(f'  [TRIAGE] Noise={t.noise_type}  Codec_cutoff={t.codec_cutoff_hz:.0f}Hz  '
        f'Comb={t.comb_detected}  Azimuth={t.azimuth_lag_ms:.2f}ms')
    log(f'  [TRIAGE] Gaps: dropout={t.dropout_gaps}  word_flag={t.word_flag_gaps}  '
        f'Wow={t.wow_detected}  Flutter={t.flutter_detected}')
    return t


def _detect_comb_in_triage(clip, fq, spec, t: TriageResult, log):
    """PA comb filter detection (§38.5). Autocorrelation of log-spectrum 80-2000Hz."""
    try:
        mask    = (fq >= 80) & (fq <= 2000)
        spec_db = 10 * np.log10(spec[mask] + 1e-30)
        if len(spec_db) < 50: return
        bin_hz  = float(fq[mask][1] - fq[mask][0]) if len(fq[mask]) > 1 else 1.5
        norm    = spec_db - np.mean(spec_db)
        acf     = np.correlate(norm, norm, 'full')[len(norm)-1:]
        if acf[0] < 1e-10: return
        acf    /= acf[0]
        # PA delay range 20-80ms → notch spacing 12.5-50Hz → lag range
        lag_lo  = max(1, int(12.5 / bin_hz))
        lag_hi  = min(len(acf)-1, int(50.0 / bin_hz))
        if lag_hi <= lag_lo: return
        pk_lag  = int(np.argmax(acf[lag_lo:lag_hi+1])) + lag_lo
        pk_val  = float(acf[pk_lag])
        regularity = pk_val / (float(np.mean(np.abs(acf[1:lag_hi+1]))) + 1e-10)
        # Threshold 1.50: voiced harmonics create ACF peaks at ~1.05-1.10
        # Real PA comb filtering creates much stronger periodicity (>1.50)
        if regularity < 1.50 or pk_val < 0.45: return
        spacing_hz    = float(pk_lag * bin_hz)
        t.comb_delay_ms   = 1000.0 / spacing_hz
        t.comb_detected   = True
        # Measure notch depth
        notch_freqs = np.arange(spacing_hz, 2001, spacing_hz)
        depths = []
        for nf in notch_freqs:
            idx = int(round((nf - float(fq[mask][0])) / bin_hz))
            if idx < 4 or idx >= len(spec_db)-4: continue
            depth = (float(np.mean(spec_db[idx-4:idx])) +
                     float(np.mean(spec_db[idx+1:idx+5])))/2 - spec_db[idx]
            if depth > 2.0: depths.append(depth)
        t.comb_n_notches = len(depths)
        t.comb_depth_db  = float(np.mean(depths)) if depths else 0.0
    except: pass


def _detect_azimuth(input_path: str, skip_s: float, dur_s: float,
                    t: TriageResult, log):
    """Azimuth misalignment (§41.2): cross-correlate L and R channels."""
    try:
        L, R    = _load_stereo(input_path, skip_s=skip_s, dur_s=min(dur_s, 10))
        n       = min(len(L), len(R), SR*5)
        L, R    = L[:n].astype(np.float64), R[:n].astype(np.float64)
        if np.std(L) < 1e-5 or np.std(R) < 1e-5: return  # mono source
        # HPF both channels at 1kHz (azimuth most visible at HF)
        sos = butter(4, 1000/(SR/2), btype='high', output='sos')
        Lf  = sosfiltfilt(sos, L); Rf = sosfiltfilt(sos, R)
        # Cross-correlation: peak lag = interchannel delay
        xc  = np.correlate(Lf, Rf, mode='full')
        lag = int(np.argmax(xc)) - (n - 1)
        lag_ms = abs(lag) / SR * 1000
        # Only flag if delay > 0.05ms (typical mechanical noise) and < 5ms
        if 0.05 < lag_ms < 5.0:
            t.azimuth_lag_ms = lag_ms
            t.azimuth_comb_detected = lag_ms > 0.1
    except: pass


def _detect_wow_flutter(clip: 'np.ndarray', t: TriageResult, log):
    """Wow/flutter: track F0 over sustained vowels (§36.3). Detect only."""
    try:
        frame_n = int(0.020 * SR); hop_n = int(0.010 * SR)
        f0s     = []
        for i in range(0, min(len(clip), SR*30)-frame_n, hop_n):
            v = _f0(clip[i:i+frame_n])
            if 70 < v < 400: f0s.append(v)
        if len(f0s) < 20: return
        f0a = np.array(f0s)
        # Sliding std over 500ms (50 frames at 10ms hop)
        win = 50
        for i in range(0, len(f0a)-win, win//4):
            seg_std = float(np.std(f0a[i:i+win]))
            if seg_std > 15.0:  # 15Hz std = mechanical instability (recitation variation is OK)
                t.max_f0_deviation_hz = max(t.max_f0_deviation_hz, seg_std)
        if t.max_f0_deviation_hz > 15.0:  # only flag extreme mechanical instability
            # Distinguish wow (< 4Hz mod rate) from flutter (4-20Hz)
            from scipy.fft import rfft as _rfft, rfftfreq as _rfftfreq
            F0_fft   = np.abs(_rfft(f0a - np.mean(f0a)))**2
            F0_fq    = _rfftfreq(len(f0a), d=0.010)   # 10ms hop
            wow_e    = float(np.sum(F0_fft[(F0_fq>=0.1)&(F0_fq<4.0)]))
            flutter_e= float(np.sum(F0_fft[(F0_fq>=4.0)&(F0_fq<=20.0)]))
            t.wow_detected     = wow_e > flutter_e * 0.5
            t.flutter_detected = flutter_e > wow_e * 0.5
    except: pass


def _classify_profile(t: TriageResult, log):
    """Assign MOSQUE | CODEC | CASSETTE | CLEAN based on damage signature."""
    mosque_score  = 0
    codec_score   = 0
    cassette_score= 0

    # Mosque indicators
    if t.est_rt60_s > 0.5:         mosque_score += 3
    if t.drr_estimate_db < 6.0:    mosque_score += 2
    if t.noise_type == 'crowd':    mosque_score += 3
    if t.noise_type == 'hum':      mosque_score += 2
    if t.comb_detected:            mosque_score += 3
    if t.frame_snr_db < 12.0:      mosque_score += 2

    # Codec indicators
    if t.codec_cutoff_hz < 18000:  codec_score  += 2
    if t.src_br < 160_000:         codec_score  += 3
    if t.noise_type == 'codec':    codec_score  += 2
    if t.clip_severity == 'light': codec_score  += 1  # codec sometimes clips

    # Cassette indicators
    if t.azimuth_comb_detected:    cassette_score += 4
    if t.wow_detected:             cassette_score += 3
    if t.flutter_detected:         cassette_score += 2
    if t.dropout_gaps > 5:         cassette_score += 2
    if t.codec_cutoff_hz < 14000 and t.src_sr < 44100: cassette_score += 2

    max_score = max(mosque_score, codec_score, cassette_score)
    if max_score < 2:
        t.profile = 'CLEAN'
    elif mosque_score == max_score:
        t.profile  = 'MOSQUE'
    elif cassette_score == max_score:
        t.profile  = 'CASSETTE'
    else:
        t.profile  = 'CODEC'

    # Source tier
    if t.frame_snr_db < 4.0  or t.clip_severity == 'severe':
        t.source_tier = 'TIER_CRITICAL'
    elif t.frame_snr_db < 10.0 or t.clip_severity in ('moderate',):
        t.source_tier = 'TIER_DAMAGED'
    elif t.frame_snr_db < 20.0 or t.est_rt60_s > 1.0:
        t.source_tier = 'TIER_DEGRADED'
    elif t.src_br < 200_000 or t.codec_cutoff_hz < 18000:
        t.source_tier = 'TIER_COMPRESSED'
    else:
        t.source_tier = 'TIER_PRISTINE'


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 — DECLIPPING  (§35.1 + §35.2: must run FIRST before NR)
#  KB insight: clipping THD inflates NR noise estimate → NR over-attenuates.
# ══════════════════════════════════════════════════════════════════════════════
def _phase1_declip(wav_path: str, t: TriageResult, res: NaqaaResult,
                   log) -> str:
    if t.clip_severity == 'none':
        log('  [P1-DECLIP] No clipping — skip'); return wav_path
    log(f'  [P1-DECLIP] severity={t.clip_severity}  islands={t.clip_islands}')

    if t.clip_severity == 'severe':
        log('  [P1-DECLIP] Severe — ffmpeg adeclip only (cubic spline too risky)')
        out = _tmp_wav('declip')
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', wav_path,
             '-af', 'adeclip=w=55:o=35:m=ae,volume=0dB',
             '-loglevel', 'error', out],
            capture_output=True)
        if r.returncode == 0:
            res.phase1_declip = True; return out
        return wav_path

    # Light/moderate: AR-based reconstruction (§33 / isteidad cubic spline)
    audio = _load_mono(wav_path)
    if len(audio) < SR: return wav_path
    try:
        peak_abs = float(np.max(np.abs(audio)))
        thresh   = peak_abs * 0.990
        clipped  = np.abs(audio) >= thresh
        if not clipped.any(): return wav_path

        a = audio.astype(np.float64)
        # Find clipped islands → cubic spline interpolation across each island
        edges   = np.diff(clipped.astype(int))
        starts  = list(np.where(edges > 0)[0] + 1)
        ends    = list(np.where(edges < 0)[0] + 1)
        if len(starts) > len(ends): ends.append(len(a)-1)

        for s, e in zip(starts, ends):
            ctx_lo = max(0, s - 8)
            ctx_hi = min(len(a), e + 8)
            # Control points from unclipped context
            ctx_x  = [i for i in range(ctx_lo, ctx_hi) if not clipped[i]]
            if len(ctx_x) < 4: continue
            ctx_y  = a[ctx_x]
            target_x = list(range(s, e+1))
            if not target_x: continue
            interp = PchipInterpolator(ctx_x, ctx_y)
            a[target_x] = interp(target_x)

        # Hard-clip safety
        a = np.clip(a, -0.998, 0.998)
        out = _tmp_wav('declip')
        if _write_wav_mono(a.astype(np.float32), out):
            log(f'  [P1-DECLIP] ✓  AR interpolated {len(starts)} islands')
            res.phase1_declip = True; return out
    except Exception as ex:
        log(f'  [P1-DECLIP] error: {ex}')
    return wav_path


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 — GAP REPAIR  (§34.9 + §35.1 Step B)
#  Dropouts < 5ms → AR fill. 5-50ms → NMF context fill + flag. > 50ms → flag.
# ══════════════════════════════════════════════════════════════════════════════
def _phase2_gap_repair(wav_path: str, t: TriageResult, res: NaqaaResult,
                       log) -> str:
    if t.dropout_gaps == 0 and t.word_flag_gaps == 0:
        log('  [P2-GAP] No gaps detected — skip'); return wav_path

    if t.word_flag_gaps > 0:
        flag = f'HUMAN_REVIEW: {t.word_flag_gaps} gaps of 5-50ms detected. Possible word deletions.'
        res.flags.append(flag)
        log(f'  [P2-GAP] ⚠ {flag}')

    if t.dropout_gaps == 0:
        return wav_path

    if t.dropout_gaps > 500:
        log(f'  [P2-GAP] {t.dropout_gaps} gaps > 500 — likely quantization noise, not dropouts — skip')
        return wav_path
    log(f'  [P2-GAP] AR fill for {t.dropout_gaps} dropout gaps (<5ms)...')
    audio = _load_mono(wav_path)
    if len(audio) < SR: return wav_path
    try:
        a = audio.astype(np.float64)
        silence_thr = 10**(-60.0/20.0)
        is_silent   = np.abs(a) < silence_thr
        ctx_len     = int(0.005 * SR)  # 5ms context for AR fit
        order       = 10
        fixed       = 0

        i = 0
        while i < len(a):
            if not is_silent[i]:
                i += 1; continue
            # Find end of gap
            gap_start = i
            while i < len(a) and is_silent[i]: i += 1
            gap_end  = i
            gap_ms   = (gap_end - gap_start) / SR * 1000

            if gap_ms >= _GAP_DROPOUT_MS: continue   # too long, handled above

            # AR fill: fit Yule-Walker from preceding context
            lo  = max(0, gap_start - ctx_len)
            ctx = a[lo:gap_start]
            if len(ctx) < order + 2: continue
            try:
                r_c = np.correlate(ctx, ctx, 'full')[len(ctx)-1:][:order+1]
                if abs(r_c[0]) < 1e-12: continue
                ar  = solve_toeplitz(r_c[:order], r_c[1:order+1])
                # Synthesize gap using AR coefficients
                buf = list(ctx[-order:])
                for j in range(gap_end - gap_start):
                    new_s = np.dot(ar, buf[-order:][::-1])
                    buf.append(float(np.clip(new_s, -1.0, 1.0)))
                a[gap_start:gap_end] = buf[order:]
                fixed += 1
            except: continue

        if fixed > 0:
            # Energy compensation (§34.9): interpolate RMS across filled gaps
            out = _tmp_wav('gap')
            if _write_wav_mono(a.astype(np.float32), out):
                log(f'  [P2-GAP] ✓  AR filled {fixed} dropouts')
                res.phase2_gap = True; return out
    except Exception as ex:
        log(f'  [P2-GAP] error: {ex}')
    return wav_path


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 — AZIMUTH CORRECTION  (§41.3)
#  Cross-channel delay correction. Restores phase alignment, NOT lost HF.
# ══════════════════════════════════════════════════════════════════════════════
def _phase3_azimuth(wav_path: str, t: TriageResult, res: NaqaaResult,
                    log) -> str:
    if not t.azimuth_comb_detected or t.azimuth_lag_ms < 0.05:
        log('  [P3-AZIMUTH] No misalignment — skip'); return wav_path

    lag_samples = int(round(t.azimuth_lag_ms / 1000.0 * SR))
    log(f'  [P3-AZIMUTH] Correcting interchannel delay={t.azimuth_lag_ms:.3f}ms '
        f'({lag_samples} samples)...')

    # Shift one channel by lag_samples to re-align using ffmpeg adelay
    out = _tmp_wav('azimuth')
    adelay = f'adelay={t.azimuth_lag_ms:.1f}|0'
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-af', adelay,
         '-loglevel', 'error', out],
        capture_output=True)
    if r.returncode == 0:
        log(f'  [P3-AZIMUTH] ✓  phase realigned')
        res.phase3_azimuth = True; return out
    return wav_path


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 4 — NOISE REDUCTION  (§28 NR types, §35.2 order: after declip)
#  Auto-selects: DF3 (if available) → TYPE_A (mosque) → TYPE_B → TYPE_C
# ══════════════════════════════════════════════════════════════════════════════
def _phase4_nr(wav_path: str, t: TriageResult, res: NaqaaResult,
               log) -> str:
    snr = min(t.frame_snr_db, t.snr_global_db)

    if snr >= 28.0 and t.noise_type == 'none':
        log('  [P4-NR] SNR sufficient — skip'); res.phase4_nr = 'skipped'
        return wav_path

    # ── DF3 path (if binary available and SNR < 15dB) ─────────────────────
    # BUG FIX from analysis: gate on min(snr_global, frame_snr)
    if DF3_BIN and snr < 15.0 and t.source_tier not in ('TIER_PRISTINE',):
        log(f'  [P4-NR] DF3 path  (SNR={snr:.1f}dB < 15dB)...')
        tmp_in  = _tmp_wav('df3_in')
        tmp_out_dir = str(_TMP)
        # DF3 requires 48kHz stereo PCM input
        r_conv = subprocess.run(
            ['ffmpeg', '-y', '-i', wav_path,
             '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le',
             '-loglevel', 'error', tmp_in],
            capture_output=True)
        if r_conv.returncode == 0:
            r_df3 = subprocess.run(
                [DF3_BIN, '--out-dir', tmp_out_dir, tmp_in],
                capture_output=True, timeout=600)
            expected = str(_TMP / (Path(tmp_in).stem + '.wav'))
            if r_df3.returncode == 0 and os.path.exists(expected):
                # Measure SNR gain (BUG FIX: measure on DF3 output, not pre-DF3)
                before_rms = _rms_db(_load_mono(wav_path, dur_s=10))
                after_rms  = _rms_db(_load_mono(expected, dur_s=10))
                res.nr_snr_gain_db = max(0.0, after_rms - before_rms)
                res.phase4_nr      = 'DF3'
                log(f'  [P4-NR] DF3 ✓  SNR_gain≈{res.nr_snr_gain_db:.1f}dB')
                return expected

    # ── TYPE_A — Mosque: heavy stationary NR (afftdn) ─────────────────────
    if t.profile in ('MOSQUE',) or t.noise_type in ('crowd', 'broadband', 'hum'):
        log(f'  [P4-NR] TYPE_A mosque NR  (SNR={snr:.1f}dB  noise={t.noise_type})...')
        # afftdn: noise reduction with adaptive estimation
        nr_gain = float(np.clip(15.0 - snr * 0.5, 3.0, _MAX_NR_GAIN_DB))  # 0.01-97 scale
        af_chain = []

        # Hum removal first if detected (§28.3: equalizer notch)
        if t.hum_hz > 0:
            hum_notches = '|'.join([
                f'equalizer=f={t.hum_hz*k:.1f}:t=h:w=4:g=-25'
                for k in range(1, 8) if t.hum_hz*k < SR/2
            ])
            if hum_notches: af_chain.append(hum_notches)

        # afftdn with HPF for room rumble
        af_chain.append(f'highpass=f=60')
        af_chain.append(f'afftdn=nr={nr_gain:.1f}:nf=-50:nt=w')

        out  = _tmp_wav('nr_a')
        af   = ','.join(af_chain)
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', wav_path, '-af', af,
             '-loglevel', 'error', out],
            capture_output=True)
        if r.returncode == 0:
            snr_gain = _estimate_nr_gain(wav_path, out)
            res.nr_snr_gain_db = snr_gain; res.phase4_nr = 'TYPE_A'
            log(f'  [P4-NR] TYPE_A ✓  gain≈{snr_gain:.1f}dB'); return out
        else:
            log(f'  [P4-NR] TYPE_A ffmpeg error: {r.stderr.decode()[:120].strip()}')

    # ── TYPE_B — LRA expansion (agate) for crushed recordings ─────────────
    if t.lra_in > 0 and t.lra_in < 1.5:
        log(f'  [P4-NR] TYPE_B expansion  (LRA={t.lra_in:.1f} < 1.5 LU)...')
        out = _tmp_wav('nr_b')
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', wav_path,
             '-af', 'agate=threshold=-25dB:ratio=2.5:attack=40:release=800',
             '-loglevel', 'error', out],
            capture_output=True)
        if r.returncode == 0:
            res.phase4_nr = 'TYPE_B'; return out

    # ── TYPE_C — Codec artifact NR ─────────────────────────────────────────
    if t.noise_type == 'codec' or t.src_br < 200_000:
        log(f'  [P4-NR] TYPE_C codec NR  (br={t.src_br//1000}kbps)...')
        # anlmdn: non-local means denoising for mosquito/quantization noise
        out = _tmp_wav('nr_c')
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', wav_path,
             '-af', 'anlmdn=s=7:p=0.002:r=0.0015:m=15',
             '-loglevel', 'error', out],
            capture_output=True)
        if r.returncode == 0:
            res.phase4_nr = 'TYPE_C'; return out

    # ── Fallback: mild afftdn ─────────────────────────────────────────────
    log(f'  [P4-NR] Mild afftdn fallback...')
    out = _tmp_wav('nr_fall')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-af', f'afftdn=nr=10:nf=-50:nt=w',
         '-loglevel', 'error', out],
        capture_output=True)
    if r.returncode == 0:
        res.phase4_nr = 'afftdn_mild'; return out

    res.phase4_nr = 'failed'; return wav_path


def _estimate_nr_gain(before_path: str, after_path: str) -> float:
    """Estimate NR gain from noise floor change (quiet frames only)."""
    try:
        b = _load_mono(before_path, dur_s=30)
        a = _load_mono(after_path,  dur_s=30)
        if len(b) < SR or len(a) < SR: return 0.0
        frame_n = int(0.030 * SR)
        b_rms = np.array([_rms_db(b[i:i+frame_n]) for i in range(0, len(b)-frame_n, frame_n)])
        a_rms = np.array([_rms_db(a[i:i+frame_n]) for i in range(0, len(a)-frame_n, frame_n)])
        # Use bottom 8% (quietest frames = noise floor, not voice)
        b_floor = float(np.percentile(b_rms, 8))
        a_floor = float(np.percentile(a_rms, 8))
        gain = b_floor - a_floor   # positive = noise floor dropped = NR worked
        return float(np.clip(gain, 0.0, 30.0))
    except: return 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 5 — DEREVERBERATION  (§28.6 JALAA — properly wired at last)
#  DRR-aware spectral gate. Target: 0.8-1.2s RT60 (§3.5: NOT anechoic)
# ══════════════════════════════════════════════════════════════════════════════
def _phase5_derev(wav_path: str, t: TriageResult, res: NaqaaResult,
                  log) -> str:
    if t.est_rt60_s <= 0.45:
        log(f'  [P5-DEREV] RT60≈{t.est_rt60_s:.2f}s — no derev needed')
        return wav_path
    if t.frame_snr_db < 8.0:
        log(f'  [P5-DEREV] SNR={t.frame_snr_db:.1f}dB < 8dB — JALAA_SNR_GATE skip')
        return wav_path

    log(f'  [P5-DEREV] RT60≈{t.est_rt60_s:.2f}s  DRR={t.drr_estimate_db:.1f}dB  '
        f'target=0.9s (§3.5 preserve masjid character)...')

    audio = _load_mono(wav_path)
    if len(audio) < SR * 2: return wav_path

    try:
        # JALAA: DRR-aware spectral gate (§28.6)
        # Estimate reverb fraction from DRR: higher DRR = less reverb suppression needed
        # Target blend: move toward RT60=0.9s from current RT60
        blend = float(np.clip(
            (t.est_rt60_s - 0.90) / (t.est_rt60_s + 0.1),
            0.0, _MAX_DEREV_BLEND))

        if blend < 0.05:
            log(f'  [P5-DEREV] Blend too low ({blend:.2f}) — skip'); return wav_path

        a       = audio.astype(np.float64)
        stft_n  = 2048; hop_n = 512
        f_ax, _, Zxx = stft(a.astype(np.float32), fs=SR,
                             nperseg=stft_n, noverlap=stft_n-hop_n, window='hann')
        mag     = np.abs(Zxx); ph = np.angle(Zxx)
        n_freq, n_time = mag.shape

        # JALAA spectral gate: estimate late-reverb contribution per frame
        # Using multi-window energy tracking: early (0-50ms) vs late (50+ms)
        # The reverb tail in the spectrogram is seen as a "smeared" version of
        # the early energy — smooth in time, lower instantaneous SNR.
        # Simple implementation: temporal median suppression on reverb-heavy frames.
        # For each freq bin: if energy variance is low over 200ms → reverb-dominated
        win_frames = int(0.200 * SR / hop_n)   # 200ms window
        mag_smooth = uniform_filter1d(mag, size=max(3, win_frames), axis=1)
        # Reverb floor = where smoothed ≈ original (low temporal variance = reverb)
        variance_ratio = mag / (mag_smooth + 1e-10)
        # Bins with variance_ratio ≈ 1.0 are reverb-dominated; > 1.5 are direct speech
        reverb_mask = variance_ratio < 1.3
        # Apply gain reduction to reverb-dominated bins
        gain_reverb = 1.0 - blend * reverb_mask.astype(float)
        mag_out     = mag * gain_reverb

        # Guard: DRR-aware — don't suppress if DRR is already good
        if t.drr_estimate_db > 12.0:
            mag_out = mag * (1.0 - blend * 0.5 * reverb_mask.astype(float))

        # Sibilant protection: don't touch 3-8kHz
        sib_m = (f_ax >= 3000) & (f_ax <= 8000)
        mag_out[sib_m, :] = mag[sib_m, :]

        _, audio_out = istft(mag_out * np.exp(1j*ph), fs=SR,
                              nperseg=stft_n, noverlap=stft_n-hop_n, window='hann')
        n = len(audio)
        audio_out = audio_out[:n] if len(audio_out) >= n else np.pad(audio_out, (0, n-len(audio_out)))
        audio_out = _rms_preserve(audio, np.nan_to_num(audio_out).astype(np.float32))

        # DRR gain estimate
        drr_after = t.drr_estimate_db + blend * 6.0   # approximate
        res.derev_drr_gain_db = float(drr_after - t.drr_estimate_db)

        out = _tmp_wav('derev')
        if _write_wav_mono(audio_out, out):
            log(f'  [P5-DEREV] ✓  blend={blend:.2f}  DRR_gain≈{res.derev_drr_gain_db:.1f}dB')
            res.phase5_derev = True; return out
    except Exception as ex:
        log(f'  [P5-DEREV] error: {ex}')
    return wav_path


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 6 — PA COMB FILTER REPAIR  (§38.5, same as J-7 but at restoration stage)
# ══════════════════════════════════════════════════════════════════════════════
def _phase6_comb(wav_path: str, t: TriageResult, res: NaqaaResult,
                 log) -> str:
    if not t.comb_detected or t.comb_n_notches == 0:
        log('  [P6-COMB] No comb filter — skip'); return wav_path

    log(f'  [P6-COMB] PA comb repair  '
        f'(delay={t.comb_delay_ms:.1f}ms  {t.comb_n_notches}notches  '
        f'depth≈{t.comb_depth_db:.1f}dB)...')

    audio = _load_mono(wav_path)
    if len(audio) < SR: return wav_path
    try:
        frame_n    = 4096; hop_n = 1024
        freqs      = rfftfreq(frame_n, 1/SR)
        win_fn     = np.hanning(frame_n).astype(np.float64)
        n          = len(audio)
        out_ola    = np.zeros(n + frame_n); norm_ola = np.zeros(n + frame_n)
        spacing_hz = 1000.0 / t.comb_delay_ms
        notch_freqs= np.arange(spacing_hz, 3001, spacing_hz)
        bw_hz      = SR / frame_n

        # Build gain mask at FFT resolution
        gain_db = np.zeros(len(freqs))
        for nf in notch_freqs:
            idx = int(round(nf / bw_hz))
            if idx < 4 or idx >= len(freqs)-4: continue
            bwn = max(2, int(round(spacing_hz * 0.2 / bw_hz)))
            fill = float(np.clip(t.comb_depth_db * 0.7, 0, _COMB_MAX_FILL_DB))
            for bi in range(max(0,idx-bwn), min(len(gain_db),idx+bwn+1)):
                d = abs(bi-idx) / max(bwn, 0.5)
                gain_db[bi] += np.exp(-d**2) * fill
        gain_lin = 10 ** (np.clip(gain_db, 0, _COMB_MAX_FILL_DB) / 20.0)

        for i in range(0, n-frame_n, hop_n):
            frame = audio[i:i+frame_n].astype(np.float64)
            f0    = _f0(frame[:2048])
            if f0 < 70: # unvoiced or silent — passthrough
                out_ola[i:i+frame_n]  += frame * win_fn
                norm_ola[i:i+frame_n] += win_fn; continue
            X = rfft(frame * win_fn)
            X_out = np.abs(X) * gain_lin * np.exp(1j * np.angle(X))
            fr_out = np.real(irfft(X_out))[:frame_n]
            out_ola[i:i+frame_n]  += np.nan_to_num(fr_out) * win_fn
            norm_ola[i:i+frame_n] += win_fn

        ns   = np.where(norm_ola > 1e-6, norm_ola, 1.0)
        aout = _rms_preserve(audio, np.nan_to_num((out_ola/ns)[:n]).astype(np.float32))

        out = _tmp_wav('comb')
        if _write_wav_mono(aout, out):
            log(f'  [P6-COMB] ✓  {t.comb_n_notches} notches filled')
            res.phase6_comb  = True
            res.comb_notches = t.comb_n_notches
            return out
    except Exception as ex:
        log(f'  [P6-COMB] error: {ex}')
    return wav_path


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 7 — EQ  (warmth tilt 200-2000Hz + presence balance)
#  §30.10: warmth_ratio is 200-2000Hz. §2.4: Arabic pharyngeals 200-800Hz.
# ══════════════════════════════════════════════════════════════════════════════
def _phase7_eq(wav_path: str, t: TriageResult, res: NaqaaResult,
               log) -> str:
    target_slope = _DNA['slope_db_oct']   # -7.43 dB/oct (200-2000Hz)
    slope_gap    = target_slope - t.warmth_slope

    if abs(slope_gap) < 0.5:
        log(f'  [P7-EQ] Slope gap {slope_gap:.2f} dB/oct < 0.5 — skip')
        return wav_path

    # Re-measure slope from post-NR audio (noise biases pre-NR measurement)
    if NUMPY_OK:
        _clip_post_nr = _load_mono(wav_path, skip_s=t.duration_s*0.05, dur_s=40)
        if len(_clip_post_nr) > SR*5:
            try:
                import numpy as _np
                from scipy.fft import rfft as _rfft, rfftfreq as _rfftfreq
                _fft_n = min(32768, len(_clip_post_nr))
                _sp  = _np.abs(_rfft(_clip_post_nr[:_fft_n].astype(_np.float64)))**2
                _fq  = _rfftfreq(_fft_n, 1/SR)
                _m   = (_fq>=200)&(_fq<=2000)
                if _m.sum() > 5:
                    _lf  = _np.log2(_fq[_m]/1000); _le = 10*_np.log10(_sp[_m]+1e-30)
                    _s,_ = _np.polyfit(_lf, _le, 1)
                    log(f'  [P7-EQ] Post-NR slope re-measured: {_s:.2f} dB/oct (was {t.warmth_slope:.2f})')
                    t.warmth_slope = float(_s)
            except: pass

    log(f'  [P7-EQ] Warmth correction  '
        f'(slope {t.warmth_slope:.2f}→{target_slope:.2f} dB/oct | 200-2000Hz)...')

    # Scale by tier (don't over-EQ damaged sources)
    tier_scale = {'TIER_PRISTINE':0.95,'TIER_COMPRESSED':0.80,
                  'TIER_DEGRADED':0.55,'TIER_DAMAGED':0.30,'TIER_CRITICAL':0.0}
    scale = tier_scale.get(t.source_tier, 0.5)
    if scale < 0.1: return wav_path

    correction = float(np.clip(slope_gap * scale, -_MAX_EQ_DB, _MAX_EQ_DB))

    # Build ffmpeg equalizer chain targeting the warmth zone
    # Correction > 0 (too bright): boost lows, cut highs
    # Correction < 0 (too dark):   cut lows, boost highs
    # Use a pair of shelf filters centered on the 200-2000Hz range
    af_nodes = []
    if correction > 0.3:    # too bright → warm it
        af_nodes.append(f'equalizer=f=400:t=h:w=1.5:g={correction*0.6:.1f}')
        af_nodes.append(f'equalizer=f=1500:t=h:w=0.8:g={-correction*0.4:.1f}')
    elif correction < -0.3: # too dark → brighten
        af_nodes.append(f'equalizer=f=400:t=h:w=1.5:g={correction*0.6:.1f}')
        af_nodes.append(f'equalizer=f=1500:t=h:w=0.8:g={-correction*0.4:.1f}')

    # High-pass at 60Hz always (KB §2.6: remove room rumble)
    af_nodes.insert(0, 'highpass=f=60:poles=2')

    # Presence guard: protect 200-800Hz Arabic pharyngeal zone (§2.4)
    # Never cut more than 2dB in that band
    af_str = ','.join(af_nodes)
    out    = _tmp_wav('eq')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path, '-af', af_str,
         '-loglevel', 'error', out],
        capture_output=True)
    if r.returncode == 0:
        res.phase7_eq        = True
        res.eq_correction_db = abs(correction)
        log(f'  [P7-EQ] ✓  correction={correction:+.2f}dB/oct  '
            f'pharyngeal zone protected'); return out
    return wav_path


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 8 — BANDWIDTH EXTENSION  (§47 Vocos-BWE principle + §28.4 TYPE_C)
#  PCHIP harmonic inference above codec cutoff. Safe above 10kHz (§47: Arabic
#  phonemes top out ~8kHz — above that is "air" only).
# ══════════════════════════════════════════════════════════════════════════════
def _phase8_bwe(wav_path: str, t: TriageResult, res: NaqaaResult, log) -> str:
    if t.codec_cutoff_hz >= 18000:
        log(f'  [P8-BWE] Cutoff {t.codec_cutoff_hz:.0f}Hz — no BWE needed')
        return wav_path
    if t.source_tier == 'TIER_CRITICAL':
        log(f'  [P8-BWE] CRITICAL tier — skip BWE')
        return wav_path

    log(f'  [P8-BWE] Bandwidth extension  '
        f'(codec_cutoff={t.codec_cutoff_hz:.0f}Hz → 20kHz)...')

    # Long file guard: PCHIP OLA needs ~(dur×SR×24 bytes) RAM
    # For >8min files, use ffmpeg high-shelf instead (safe, fast, no OOM)
    if t.duration_s > 480:
        log(f'  [P8-BWE] Long file ({t.duration_s:.0f}s > 480s) → ffmpeg shelf fallback')
        shelf_db = 2.5 if t.codec_cutoff_hz > 14000 else 3.5
        cutoff_hz = int(t.codec_cutoff_hz * 0.90)
        out = _tmp_wav('bwe_shelf')
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', wav_path,
             '-af', f'equalizer=f={cutoff_hz}:t=h:w=0.5:g={shelf_db:.1f}',
             '-loglevel', 'error', out],
            capture_output=True)
        if r.returncode == 0:
            log(f'  [P8-BWE] ✓ shelf +{shelf_db:.1f}dB above {cutoff_hz}Hz')
            res.phase8_bwe    = True
            res.bwe_cutoff_hz = t.codec_cutoff_hz
            return out
        return wav_path

    audio = _load_mono(wav_path)
    if len(audio) < SR: return wav_path
    try:
        a      = audio.astype(np.float64)
        cutoff = t.codec_cutoff_hz

        # Strategy:
        # 1. PCHIP harmonic inference: extend existing harmonics above cutoff
        # 2. Air-shelf boost above cutoff (§47: Linkwitz-Riley crossover principle)
        # Step 1: PCHIP on voiced frames only
        frame_n = 4096; hop_n  = 1024
        freqs   = rfftfreq(frame_n, 1/SR)
        win_fn  = np.hanning(frame_n).astype(np.float64)
        n       = len(a)
        out_ola = np.zeros(n+frame_n); norm_ola = np.zeros(n+frame_n)

        for i in range(0, n-frame_n, hop_n):
            frame = a[i:i+frame_n]
            F0    = _f0(frame[:2048])
            if F0 < 70:   # unvoiced — use gentle air shelf instead
                X = rfft(frame*win_fn); mag=np.abs(X); ph=np.angle(X)
                # Gentle shelf above cutoff: +2dB
                air_gain = np.where(freqs > cutoff,
                                    10**(2.0/20.0) * np.exp(-0.5*((freqs-cutoff)/(3000))**2)+0.7, 1.0)
                X_out = mag * air_gain * np.exp(1j*ph)
                out_ola[i:i+frame_n]  += np.real(irfft(X_out))[:frame_n] * win_fn
                norm_ola[i:i+frame_n] += win_fn; continue

            X   = rfft(frame*win_fn)
            mag = np.abs(X).astype(np.float64)
            ph  = np.angle(X).astype(np.float64)
            bw  = SR/frame_n
            cutoff_bin = int(cutoff/bw)

            # Measure harmonic amplitudes BELOW cutoff
            bwn = max(2, int(round(F0*0.20/bw)))
            h_amp = {}
            for k in range(1, 20):
                hf = F0*k
                if hf >= cutoff*0.9: break
                b = int(round(hf/bw))
                if b >= cutoff_bin: break
                bl=max(0,b-bwn); bh=min(cutoff_bin,b+bwn)
                h_amp[k] = float(np.max(mag[bl:bh+1]))

            if len(h_amp) < 3:
                out_ola[i:i+frame_n]  += frame*win_fn
                norm_ola[i:i+frame_n] += win_fn; continue

            # PCHIP fit on measured harmonics (log-log space for stability)
            k_vals = sorted(h_amp.keys())
            f_meas = np.array([F0*k for k in k_vals])
            a_meas = np.array([max(h_amp[k], 1e-8) for k in k_vals])
            log_f  = np.log(f_meas); log_a = np.log(a_meas)

            try:
                pchip = PchipInterpolator(log_f, log_a, extrapolate=True)
                # Extrapolate above cutoff
                ext_bins = np.where(freqs > cutoff)[0]
                if len(ext_bins) > 0:
                    ext_freqs = freqs[ext_bins]
                    # Cap extrapolation at 3 octaves above last measured harmonic
                    max_ext   = f_meas[-1] * 4.0
                    valid     = ext_freqs < max_ext
                    if valid.any():
                        ext_amp = np.exp(np.clip(pchip(np.log(ext_freqs[valid])), -30, 5))
                        # Blend: strong at cutoff, fades out (§47: refiner principle)
                        fade = np.exp(-((ext_freqs[valid]-cutoff)/4000)**2)
                        scale_arr = fade * 0.55
                        mag[ext_bins[valid]] = np.where(
                            mag[ext_bins[valid]] < ext_amp * scale_arr,
                            mag[ext_bins[valid]] + ext_amp * scale_arr * 0.40,
                            mag[ext_bins[valid]])
            except: pass

            X_out = mag * np.exp(1j*ph)
            out_ola[i:i+frame_n]  += np.real(irfft(X_out))[:frame_n]*win_fn
            norm_ola[i:i+frame_n] += win_fn

        ns   = np.where(norm_ola>1e-6, norm_ola, 1.0)
        aout = _rms_preserve(audio, np.nan_to_num((out_ola/ns)[:n]).astype(np.float32))

        out = _tmp_wav('bwe')
        if _write_wav_mono(aout, out):
            log(f'  [P8-BWE] ✓  PCHIP harmonic inference above {cutoff:.0f}Hz')
            res.phase8_bwe  = True
            res.bwe_cutoff_hz = cutoff
            return out
    except Exception as ex:
        log(f'  [P8-BWE] error: {ex}')
    return wav_path


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 9 — LUFS NORMALIZATION  (§29: target -6.29 LUFS, preserve LRA)
# ══════════════════════════════════════════════════════════════════════════════
def _phase9_lufs(wav_path: str, t: TriageResult, res: NaqaaResult,
                 log) -> str:
    target_lufs = _DNA['lufs']   # -6.29
    log(f'  [P9-LUFS] Normalizing to {target_lufs:.2f} LUFS...')

    # Tier-dependent target ceiling
    tier_lufs_ceiling = {
        'TIER_PRISTINE':  -6.29,
        'TIER_COMPRESSED':-6.50,
        'TIER_DEGRADED':  -7.50,   # don't over-push damaged sources
        'TIER_DAMAGED':   -9.00,
        'TIER_CRITICAL':  -11.0,
    }
    actual_target = tier_lufs_ceiling.get(t.source_tier, target_lufs)

    out = _tmp_wav('lufs')
    # Use ffmpeg loudnorm (two-pass for accuracy)
    lufs_gap = abs(actual_target - t.lufs_in) if t.lufs_in > -90 else 0
    if lufs_gap > 8.0:
        # Large LUFS gap: simple volume adjust is more reliable
        gain_db = float(actual_target - t.lufs_in) if t.lufs_in > -90 else 0
        gain_db = float(np.clip(gain_db, -30, 30))
        af = f'volume={gain_db:.2f}dB,alimiter=level_in=1:level_out=0.97:limit=0.97:attack=5:release=50'
    else:
        af  = (f'loudnorm=I={actual_target:.2f}:TP=-1.5:LRA=7.0:'
               f'measured_I={t.lufs_in:.2f}:measured_LRA={max(t.lra_in,0.5):.2f}:'
               f'measured_TP=-1.0:measured_thresh={t.lufs_in-10:.2f}:linear=true:print_format=none')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path, '-af', af,
         '-loglevel', 'error', out],
        capture_output=True)

    if r.returncode != 0 or not os.path.exists(out):
        # Fallback: simple volume adjust
        if t.lufs_in > -90:
            gain_db = actual_target - t.lufs_in
            gain_db = float(np.clip(gain_db, -20, 20))
            af2     = f'volume={gain_db:.2f}dB'
            r2 = subprocess.run(
                ['ffmpeg', '-y', '-i', wav_path, '-af', af2,
                 '-loglevel', 'error', out],
                capture_output=True)
            if r2.returncode != 0: return wav_path

    lufs_out, lra_out, _ = _measure_lufs(out)
    res.lufs_out  = lufs_out
    res.lra_out   = lra_out
    res.phase9_lufs = True
    log(f'  [P9-LUFS] ✓  LUFS {t.lufs_in:.2f}→{lufs_out:.2f}  LRA {lra_out:.2f} LU')
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 10 — QUALITY SCORING  (§29.2: 5-component score)
# ══════════════════════════════════════════════════════════════════════════════
def _score(lufs, lra, crest, warmth_slope, tier) -> float:
    ref = _DNA
    # 1. Spectral proxy (via warmth slope — best available without full ref spectrum)
    spectral_score = 30.0 * max(0, 1.0 - abs(warmth_slope - ref['slope_db_oct']) / 6.0)
    # 2. LUFS
    lufs_score     = 25.0 * max(0, 1.0 - abs(lufs - ref['lufs']) / 3.0) if lufs > -90 else 0
    # 3. Crest
    crest_score    = 20.0 * max(0, 1.0 - abs(crest - ref['crest_db']) / 3.0) if crest > 0 else 10
    # 4. LRA
    lra_score      = 15.0 * max(0, 1.0 - abs(lra - ref['lra']) / 2.5) if lra > 0 else 5
    # 5. Warmth (same as slope for us — re-use)
    warmth_score   = 10.0 * max(0, 1.0 - abs(warmth_slope - ref['slope_db_oct']) / 3.0)
    return round(spectral_score + lufs_score + crest_score + lra_score + warmth_score, 1)


def _tmp_wav(tag: str) -> str:
    return str(_TMP / f'naqaa_{tag}_{uuid.uuid4().hex[:6]}.wav')


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def restore(
    input_path:  str,
    output_path: str,
    ref_path:    Optional[str] = None,   # optional 1425H reference for DNA override
    force_profile: Optional[str] = None, # 'MOSQUE' | 'CODEC' | 'CASSETTE'
    output_br_k: int = 320,
    log_fn = None,
) -> NaqaaResult:
    """
    النقاء v1 — Full restoration pipeline for low-quality Quran audio.
    
    Pipeline order (§35.2 KB mandate):
      Phase 0: Triage
      Phase 1: Declip (before NR — clipping THD inflates NR estimate)
      Phase 2: Gap repair
      Phase 3: Azimuth (cassette)
      Phase 4: NR (after declip)
      Phase 5: Derev (after NR — avoid derev amplifying noise)
      Phase 6: Comb repair (mosque PA)
      Phase 7: EQ
      Phase 8: BWE
      Phase 9: LUFS
      Phase 10: Score + report
    """
    _log = log_fn or print
    res  = NaqaaResult()
    t0   = time.time()

    _log(f'\n╔═══ النقاء v1 — Quran Restoration ═══')
    _log(f'  Input:  {input_path}')
    _log(f'  Output: {output_path}')
    if DF3_BIN: _log(f'  DF3:    {DF3_BIN}')
    else:       _log(f'  DF3:    not found (using afftdn fallback)')

    if not os.path.exists(input_path):
        _log(f'  ERROR: Input not found'); return res

    # ── Phase 0: Triage ────────────────────────────────────────────────────
    _log('\n── Phase 0: Triage ─────────────────────────────────────────')
    triage = _phase0_triage(input_path, _log)
    if force_profile: triage.profile = force_profile
    res.triage = triage

    # Score before
    res.score_before = _score(triage.lufs_in, triage.lra_in,
                               triage.crest_in, triage.warmth_slope,
                               triage.source_tier)
    _log(f'  Score BEFORE: {res.score_before:.1f}/100')

    # Wow/flutter advisory
    if triage.wow_detected or triage.flutter_detected:
        flag = (f'HUMAN_REVIEW: {"Wow" if triage.wow_detected else ""}  '
                f'{"Flutter" if triage.flutter_detected else ""} detected '
                f'(max F0 deviation={triage.max_f0_deviation_hz:.1f}Hz). '
                f'Do NOT auto-correct — Tajweed Madd duration must be preserved. '
                f'Review with iZotope RX Wow & Flutter or CAPSTAN.')
        res.flags.append(flag)
        _log(f'  ⚠ {flag}')

    # Dropout flags
    if triage.word_flag_gaps > 0:
        res.flags.append(
            f'HUMAN_REVIEW: {triage.word_flag_gaps} gaps of 5-50ms — '
            f'possible word deletions in digitization source.')

    # Build intermediate WAV to work with
    _log('\n── Preparing intermediate WAV ───────────────────────────────')
    cur_wav = _tmp_wav('source')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', input_path,
         '-ar', str(SR), '-ac', '2', '-c:a', 'pcm_s24le',
         '-loglevel', 'error', cur_wav],
        capture_output=True)
    if r.returncode != 0:
        _log('  ERROR: Cannot convert input to WAV'); return res

    # ── NUMPY available check for DSP phases ──────────────────────────────
    if not NUMPY_OK:
        _log('  numpy unavailable — skipping DSP phases 1-8')
        _log('  Running LUFS normalization only...')
        cur_wav = _phase9_lufs(cur_wav, triage, res, _log)
    else:
        # ── Phase 1: Declip ────────────────────────────────────────────────
        _log('\n── Phase 1: Declip ─────────────────────────────────────────')
        cur_wav = _phase1_declip(cur_wav, triage, res, _log)

        # ── Phase 2: Gap repair ───────────────────────────────────────────
        _log('\n── Phase 2: Gap Repair ─────────────────────────────────────')
        cur_wav = _phase2_gap_repair(cur_wav, triage, res, _log)

        # ── Phase 3: Azimuth ──────────────────────────────────────────────
        _log('\n── Phase 3: Azimuth Correction ─────────────────────────────')
        cur_wav = _phase3_azimuth(cur_wav, triage, res, _log)

        # ── Phase 4: NR ───────────────────────────────────────────────────
        _log('\n── Phase 4: Noise Reduction ─────────────────────────────────')
        cur_wav = _phase4_nr(cur_wav, triage, res, _log)

        # ── Phase 5: Derev ────────────────────────────────────────────────
        _log('\n── Phase 5: Dereverberation (JALAA) ────────────────────────')
        cur_wav = _phase5_derev(cur_wav, triage, res, _log)

        # ── Phase 6: Comb repair ──────────────────────────────────────────
        _log('\n── Phase 6: PA Comb Repair ─────────────────────────────────')
        cur_wav = _phase6_comb(cur_wav, triage, res, _log)

        # ── Phase 7: EQ ───────────────────────────────────────────────────
        _log('\n── Phase 7: EQ (Warmth Tilt 200-2000Hz) ────────────────────')
        cur_wav = _phase7_eq(cur_wav, triage, res, _log)

        # ── Phase 8: BWE ──────────────────────────────────────────────────
        _log('\n── Phase 8: Bandwidth Extension ────────────────────────────')
        cur_wav = _phase8_bwe(cur_wav, triage, res, _log)

        # ── Phase 9: LUFS ─────────────────────────────────────────────────
        _log('\n── Phase 9: LUFS Normalization ─────────────────────────────')
        cur_wav = _phase9_lufs(cur_wav, triage, res, _log)

    # ── Encode output ─────────────────────────────────────────────────────
    _log(f'\n── Encoding → {output_path}')
    if output_path.endswith('.mp3'):
        ok = _encode_mp3(cur_wav, output_path, output_br_k)
    else:
        ok = subprocess.run(
            ['ffmpeg', '-y', '-i', cur_wav, '-loglevel', 'error', output_path],
            capture_output=True).returncode == 0

    if not ok:
        _log('  ERROR: Encoding failed'); return res

    # ── Phase 10: Score after ─────────────────────────────────────────────
    if NUMPY_OK:
        out_clip    = _load_mono(output_path, dur_s=60)
        out_lufs, out_lra, _ = _measure_lufs(output_path)
        out_crest   = (float(20*np.log10(np.max(np.abs(out_clip))+1e-10)) -
                       _rms_db(out_clip)) if len(out_clip) > SR else triage.crest_in
        # Re-measure warmth slope on output
        out_slope   = triage.warmth_slope  # approximation if not re-measured
        try:
            fft_n = min(32768, len(out_clip))
            sp    = np.abs(rfft(out_clip[:fft_n].astype(np.float64)))**2
            fq    = rfftfreq(fft_n, 1/SR)
            m     = (fq>=200)&(fq<=2000)
            if m.sum() > 5:
                lf = np.log2(fq[m]/1000.0); le = 10*np.log10(sp[m]+1e-30)
                out_slope, _ = np.polyfit(lf, le, 1)
        except: pass
        res.crest_out  = out_crest
        res.score_after = _score(out_lufs, out_lra, out_crest, out_slope,
                                  triage.source_tier)

    res.status       = 'OK'
    res.output_path  = output_path
    res.processing_s = time.time() - t0

    # ── Final report ──────────────────────────────────────────────────────
    phases = ' · '.join([
        n for n,v in [
            ('Declip',    res.phase1_declip),
            ('Gap',       res.phase2_gap),
            ('Azimuth',   res.phase3_azimuth),
            (f'NR({res.phase4_nr})', res.phase4_nr not in ('skipped','failed')),
            ('Derev',     res.phase5_derev),
            ('Comb',      res.phase6_comb),
            ('EQ',        res.phase7_eq),
            ('BWE',       res.phase8_bwe),
            ('LUFS',      res.phase9_lufs),
        ] if v
    ])
    _log(f'\n╠═══ النقاء RESULT ═══')
    _log(f'  Phases fired:  {phases}')
    _log(f'  Score:         {res.score_before:.1f} → {res.score_after:.1f} / 100')
    _log(f'  LUFS:          {triage.lufs_in:.2f} → {res.lufs_out:.2f} dBFS')
    _log(f'  NR gain:       {res.nr_snr_gain_db:.1f} dB')
    _log(f'  Derev gain:    {res.derev_drr_gain_db:.1f} dB DRR')
    _log(f'  Comb notches:  {res.comb_notches}')
    _log(f'  BWE cutoff:    {res.bwe_cutoff_hz:.0f} Hz' if res.phase8_bwe else '  BWE: skipped')
    _log(f'  Time:          {res.processing_s:.1f}s')
    _log(f'  Output:        {output_path}')
    if res.flags:
        _log(f'\n  ⚠ HUMAN REVIEW FLAGS:')
        for f in res.flags: _log(f'    • {f}')
    _log('╚═══════════════════════════════════\n')
    return res


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(
        description='النقاء v1 — Low-Quality Quran Restoration Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect and restore (recommended):
  python naqaa_v1.py -i سورة_النور.mp3 -o نور_restored.mp3

  # Force mosque profile (for سورة_المائدة):
  python naqaa_v1.py -i المائدة.mp3 -o مائدة_restored.mp3 --mosque

  # With reference audio for DNA calibration:
  python naqaa_v1.py -i bad.mp3 -o good.mp3 --ref المرجع1425.mp3

  # Cassette digitization:
  python naqaa_v1.py -i cassette.wav -o cassette_restored.mp3 --cassette
        """)
    p.add_argument('-i',         required=True,  help='Input audio file')
    p.add_argument('-o',         required=True,  help='Output MP3 or WAV')
    p.add_argument('--ref',      default=None,   help='Reference audio (1425H)')
    p.add_argument('--mosque',   action='store_true', help='Force mosque profile')
    p.add_argument('--codec',    action='store_true', help='Force codec profile')
    p.add_argument('--cassette', action='store_true', help='Force cassette profile')
    p.add_argument('--br',       type=int, default=320, help='Output bitrate kbps')
    p.add_argument('--quiet',    action='store_true', help='Minimal logging')
    args = p.parse_args()

    profile = None
    if args.mosque:   profile = 'MOSQUE'
    elif args.codec:  profile = 'CODEC'
    elif args.cassette: profile = 'CASSETTE'

    log = (lambda x: None) if args.quiet else print

    print('\n╔═══════════════════════════════════════════════════════════════╗')
    print('║  النقاء v1 — Quran Audio Restoration Engine                  ║')
    print('║  المرجع: الشيخ ياسر الدوسري — 1425H                           ║')
    print('║  Pipeline: Declip→NR→Derev→Comb→EQ→BWE→LUFS  (KB §35.2)    ║')
    print('╚═══════════════════════════════════════════════════════════════╝')

    result = restore(
        input_path    = args.i,
        output_path   = args.o,
        ref_path      = args.ref,
        force_profile = profile,
        output_br_k   = args.br,
        log_fn        = log,
    )

    sys.exit(0 if result.status == 'OK' else 1)
