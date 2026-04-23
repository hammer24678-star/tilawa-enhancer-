#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   Audio Enhancement Engine v8.4 — "Source Tier Intelligence"              ║
║   المرجع: الشيخ ياسر الدوسري — 1425H                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  الأخطاء المُشخَّصة في v7.6 (Forensic Deep-Dive):                           ║
║                                                                              ║
║  🔴 BUG #1 — SPECTRAL_BIAS اتجاه معكوس في 3 نطاقات حرجة                   ║
║     250Hz: bias=+11 → cut بدل boost (output -7dB تحت ref!)                 ║
║     4kHz:  bias=-1.5 → boost بدل cut (output +5dB فوق ref!)                ║
║     8kHz:  bias=-4.0 → boost بدل cut (output +10dB فوق ref!)               ║
║     الإصلاح: SPECTRAL_BIAS_V8 بالاتفاقية الصحيحة (output-ref)              ║
║                                                                              ║
║  🔴 BUG #2 — Double Compand Stacking يسحق Crest                            ║
║     LRA compand + Main compand → ضغط مزدوج → Crest ينهار                  ║
║     الإصلاح: حذف LRA compand من Pass1 — Main compand وحيد                  ║
║                                                                              ║
║  🟠 BUG #3 — 5 تطبيقات alimiter تطحن Crest تراكمياً                        ║
║     P1(×2) + P2 + P3 + P4 = 5 مرات limit=0.891 → Crest ينخفض 0.8-1.5LU  ║
║     الإصلاح: WAV وسيطة = limit=0.9997 فقط | MP3 نهائي = 0.891             ║
║                                                                              ║
║  🟠 BUG #4 — build_compand_mds يستخدم DR بدل LRA                          ║
║     lra_delta = damage.dr - TARGET['dr'] ← خطأ نوع!                        ║
║     الإصلاح: lra_delta = inp_lra - ref_fp.lra_clip (صحيح)                 ║
║                                                                              ║
║  🟡 BUG #5 — Quality Gate لا يحمي Crest بشكل منفصل                        ║
║     عتبة 1.0 نقطة تتجاهل انهيار Crest 3+LU                                ║
║     الإصلاح: حارس مستقل Crest < P1-1.5LU AND < target-0.8                 ║
║                                                                              ║
║  المحافظ عليه من v7.6 (Architecture سليم):                                  ║
║  ✅ MDS System (SFM + DR + Spectral Distance + Per-Band SNR)               ║
║  ✅ SFM-Adaptive NR                                                          ║
║  ✅ Full-File LRA Target 4.19 (v7.6 fix)                                    ║
║  ✅ Dual LRA: lra_clip للـ compand | lra للـ quality score                  ║
║  ✅ 9-Segment Full-File Spectral Average                                    ║
║  ✅ 4-Pass WAV Pipeline (lossless حتى Pass4)                               ║
║  ✅ Crest-Aware Warmth Nodes                                                ║
║  ✅ Scipy Perceptual EQ (Bark + A-weight)                                   ║
║  ✅ Arabic Filename Safety                                                   ║
║                                                                              ║
║  الهدف: LUFS=-6.29 RMS=-10.01 Crest=10.25 LRA=4.19 ≥96/100               ║
║                                                                              ║
║  إصلاحات v8.1 — Android Subprocess Hardening:                               ║
║  🔴 PATCH #1 — REF_CACHE: /tmp → Path.home()/.tilawa_cache/ (persistent)   ║
║  🔴 PATCH #2 — REF_FILES: hardcoded → env var + ~/.tilawa_ref/ + legacy     ║
║  🔴 PATCH #3 — ALL /tmp/ refs → tempfile.gettempdir() (Android-safe)        ║
║  🟠 PATCH #4 — Adaptive EQ scale: tiered → linear ramp (+3 quality pts)    ║
║  🟡 PATCH #5 — 64K_FLOOR label: honest Crest ceiling for 64kbps sources    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, warnings, time, tempfile as _tempfile, copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
warnings.filterwarnings('ignore')

# v8.1 PATCH #3: platform/context-aware temp dir
# Termux shell:       /data/data/com.termux/files/usr/tmp/
# Android subprocess: /data/local/tmp/ or app cache dir
# Linux desktop:      /tmp/
_TMP = _tempfile.gettempdir()

try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    from scipy.optimize import minimize
    from scipy.interpolate import CubicSpline
    NUMPY_OK = SCIPY_OK = True
except ImportError:
    NUMPY_OK = SCIPY_OK = False

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
SR = 48000

TARGET = {
    'lufs':      -6.29,
    'rms':      -10.01,
    'crest':     10.25,
    'lra':        4.19,   # full-file measurement (corrected in v7.6, kept in v8)
    'true_peak':  -1.0,
    'bitrate':  '320k',
    'sfm':        0.0444,
    'dr':          7.9,
}

# ── v8.1 PATCH #2: REF_FILES — env var → home dir → legacy (dev only) ─────
def _resolve_ref_files() -> List[str]:
    """
    Resolution order:
      1. TILAWA_REF_DIR env var (set by Flutter before spawning subprocess)
      2. ~/.tilawa_ref/ (user-populated in Termux home)
      3. Legacy /mnt/user-data/uploads/ (Claude.ai sandbox — dev only)
    Returns [] if nothing found; get_reference_fingerprint() handles empty list.
    """
    # 1. Flutter sets this env var before Process.start()
    env_dir = os.environ.get('TILAWA_REF_DIR', '')
    if env_dir and os.path.isdir(env_dir):
        found = sorted([str(p) for p in Path(env_dir).glob('*.mp3')])
        if found: return found
    # 2. Termux home ref directory (user populates this once)
    home_ref = Path.home() / '.tilawa_ref'
    if home_ref.is_dir():
        found = sorted([str(p) for p in home_ref.glob('*.mp3')])
        if found: return found
    # 3. v8.2: Docker /app/reference_audio/ self-location
    container_ref = Path(__file__).parent / "reference_audio"
    if container_ref.is_dir():
        found = sorted([
            str(p) for p in container_ref.glob("*.mp3")
            if p.stat().st_size > 10_000
        ])
        if found:
            return found
    # 4. Legacy Claude.ai sandbox paths (development only)
    legacy = [
        "/mnt/user-data/uploads/ref_araf_1425h.mp3",
        "/mnt/user-data/uploads/ref_fath_1425h.mp3",
        "/mnt/user-data/uploads/ref_fatir_1425h.mp3",
    ]
    found = [p for p in legacy if os.path.exists(p)]
    return found

REF_FILES = _resolve_ref_files()

# ── v8.1 PATCH #1: REF_CACHE — persistent home-dir path ─────────────────────
# /tmp/ does NOT exist in Android's app subprocess sandbox.
# Path.home() resolves correctly in both Termux shell and Flutter subprocess.
_CACHE_DIR = Path.home() / '.tilawa_cache'
REF_CACHE   = str(_CACHE_DIR / 'ref_fp.v87.json')   # v8.5: cache version bump

CENTERS_31 = [
    20,25,31.5,40,50,63,80,100,125,160,
    200,250,315,400,500,630,800,1000,1250,1600,
    2000,2500,3150,4000,5000,6300,8000,10000,12500,16000,20000,
]

A_WEIGHT: Dict[float,float] = {
    20:-50.5,25:-44.7,31.5:-39.4,40:-34.6,50:-30.2,
    63:-26.2,80:-22.5,100:-19.1,125:-16.1,160:-13.4,
    200:-10.9,250:-8.6,315:-6.6,400:-4.8,500:-3.2,
    630:-1.9,800:-0.8,1000:0.0,1250:0.6,1600:1.0,
    2000:1.2,2500:1.3,3150:1.2,4000:1.0,5000:0.5,
    6300:-0.1,8000:-1.1,10000:-2.5,12500:-4.3,16000:-6.6,20000:-9.3,
}

# ══════════════════════════════════════════════════════════════════════════════
#  v8 BUG #1 FIX — SPECTRAL_BIAS_V8: اتفاقية صحيحة موحدة
#
#  الاتفاقية: bias = (output - ref)
#    سالب  = output تحت ref   → g = -(-)*scale = موجب (boost) ✅
#    موجب  = output فوق ref   → g = -(+)*scale = سالب (cut)  ✅
#
#  v7.6 كان يستخدم "رغبة في التصحيح" بدل "الخطأ المُقاس":
#    250Hz: +11 → يقطع بدل رفع (output -7dB تحت ref) ❌
#    4kHz:  -1.5 → يرفع بدل قطع (output +5dB فوق ref) ❌
#    8kHz:  -4.0 → يرفع بدل قطع (output +10dB فوق ref) ❌
# ══════════════════════════════════════════════════════════════════════════════
SPECTRAL_BIAS_V8: Dict[int,float] = {
    # النطاقات الدنيا — محتاج رفع (output تحت ref في ملفات 64kbps)
    80:    -2.50,   # output -2.5dB تحت ref → g=+0.625dB boost
    100:   -4.00,   # output -4dB تحت ref  → g=+1.00dB boost
    125:   +3.50,   # output +3.5dB فوق ref → g=-0.875dB cut
    200:   -4.00,   # output -4dB تحت ref  → g=+1.00dB boost
    # ↓ إصلاح v8 الحرج: كان +11.00 → يقطع عوضاً عن الرفع!
    250:   -7.00,   # output -7dB تحت ref  → g=+1.75dB boost ← v8 FIX الأكبر
    315:   +6.00,   # output +6dB فوق ref  → g=-1.50dB cut
    400:   -1.50,   # output تحت ref      → g=+0.375dB boost
    500:   +1.50,   # output فوق ref      → g=-0.375dB cut
    630:   -2.50,   # output تحت ref      → g=+0.625dB boost
    800:   +1.50,   # output فوق ref      → g=-0.375dB cut
    1000:  -1.00,   # output تحت ref      → g=+0.25dB boost (v7.55: كان يعطي قطع)
    1250:  +0.40,   # صغير جداً → تأثير ضئيل
    2000:  +0.50,   # صغير جداً → تأثير ضئيل
    2500:  +1.80,   # output فوق ref      → g=-0.45dB cut
    3150:  +1.20,   # output فوق ref      → g=-0.30dB cut
    # ↓ إصلاح v8 الحرج: كان -1.50 → يرفع عوضاً عن القطع!
    4000:  +5.00,   # output +5dB فوق ref  → g=-1.25dB cut ← v8 FIX
    # ↓ إصلاح v8: كان -0.80 و-0.90 → يرفع في منطقة مرتفعة أصلاً
    5000:  +0.80,   # output فوق ref      → g=-0.20dB cut ← v8 FIX (was -0.80)
    6300:  +0.90,   # output فوق ref      → g=-0.225dB cut ← v8 FIX (was -0.90)
    # ↓ إصلاح v8 الحرج: كان -4.00 → يرفع عوضاً عن القطع!
    8000:  +8.00,   # output +8-10dB فوق ref → g=-2.00dB cut ← v8 FIX الأكبر
    10000: -2.00,   # output تحت ref (rolloff) → g=+0.50dB boost
}
BIAS_SCALE = 0.25   # الصيغة: g = round(-bias_db * BIAS_SCALE, 2)

# ══════════════════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReferenceFingerprint:
    third_oct:     Dict[float,float] = field(default_factory=dict)
    a_weighted:    Dict[float,float] = field(default_factory=dict)
    rms:           float = TARGET['rms']
    peak:          float = TARGET['true_peak']
    crest:         float = TARGET['crest']
    lra:           float = TARGET['lra']
    lra_clip:      float = 2.94
    tilt_slope:    float = 0.0
    warmth_ratio:  float = 0.0
    sfm:           float = TARGET['sfm']
    dr:            float = TARGET['dr']
    n_files:       int   = 0
    # ── v8.45: DeepReferenceModel fields ─────────────────────────────────────
    phrase_lra_p10:       float = 2.50   # LRA at 10th percentile of phrases
    phrase_lra_p50:       float = 3.37   # LRA at 50th percentile (compand target)
    phrase_lra_p90:       float = 4.20   # LRA at 90th percentile
    silence_floor_db:     float = -73.0  # measured ref noise floor (NR ceiling = this - 3dB)
    ref_codec_cutoff_hz:  float = 14000.0 # highest freq with real content in refs
    peak_distribution:    str   = 'uniform'  # front_loaded / uniform / back_loaded

@dataclass
class DamageProfile:
    """v7.6 Multi-Metric Damage Score (MDS) — محافَظ عليه في v8"""
    snr:            float = 30.0
    sfm:            float = 0.05
    dr:             float = 8.0
    hf_deficit:     float = 0.0
    spectral_dist:  float = 0.0
    crest:          float = 10.0
    src_br:         int   = 128000
    band_snr:       Dict[float,float] = field(default_factory=dict)
    mds:            float = 0.0
    nr_intensity:   float = 0.0
    compand_score:  float = 0.0
    has_ringing:    bool  = False
    rolloff_hz:     float = 20000.0
    quality_label:  str   = 'GOOD'

@dataclass
class QualityReport:
    score:       float = 0.0
    spectral:    float = 0.0
    lufs:        float = 0.0
    crest:       float = 0.0
    lra:         float = 0.0
    warmth:      float = 0.0
    hf:          float = 0.0
    avg_err:     float = 99.0
    warmth_tilt: float = 0.0
    warmth_ref:  float = 0.0
    lra_target:  float = TARGET['lra']
    notes:       List[str] = field(default_factory=list)
    # ── v8.5: TierAdjustedScoring fields ─────────────────────────────────────
    score_absolute: float = 0.0   # scored vs original 1425H targets (always)
    score_tier:     float = 0.0   # scored vs tier-achievable targets (displayed)
    ceiling_reason: str   = ''    # e.g. "TIER_COMPRESSED: Crest≤9.8LU  LRA≤4.0LU



# ══════════════════════════════════════════════════════════════════════════════
#  v8.6 — SilenceProfile + measure_silence_floor()
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SilenceProfile:
    floor_dbfs:       float = -62.0
    hum_50hz_db:      float = 0.0
    hum_60hz_db:      float = 0.0
    hum_100hz_db:     float = 0.0
    hum_120hz_db:     float = 0.0
    noise_sfm:        float = 0.1
    n_silence_frames: int   = 0
    valid:            bool  = False


def measure_silence_floor(audio: 'np.ndarray', sr: int = SR) -> SilenceProfile:
    frame_n = int(0.2 * sr)
    if len(audio) < frame_n * 6:
        return SilenceProfile(valid=False)
    overall_db    = float(20 * np.log10(np.sqrt(np.mean(audio**2)) + 1e-10))
    silence_ceil  = overall_db - 18.0
    silence_lim   = -62.0
    frames        = [audio[i:i+frame_n] for i in range(0, len(audio)-frame_n, frame_n)]
    sil_frames    = [f for f in frames
                     if silence_lim < float(20*np.log10(np.sqrt(np.mean(f**2))+1e-10)) < silence_ceil]
    if len(sil_frames) < 3:
        return SilenceProfile(valid=False)
    sa            = np.concatenate(sil_frames)
    floor_db      = float(20 * np.log10(np.sqrt(np.mean(sa**2)) + 1e-10))
    N             = len(sa)
    spec          = np.abs(rfft(sa))**2
    freqs         = rfftfreq(N, 1.0/sr)
    def _be(fc, bw=3.0):
        m = (freqs>=fc-bw)&(freqs<=fc+bw); return float(np.mean(spec[m])) if m.sum()>0 else 1e-30
    def _hdb(fc):
        nb = np.mean([_be(fc-25.0), _be(fc+25.0)])
        return float(10*np.log10(_be(fc)/(nb+1e-30)+1e-30))
    ms            = (freqs>=200.0)&(freqs<=8000.0); s = spec[ms]; eps=1e-10
    noise_sfm     = float(np.clip(np.exp(np.mean(np.log(s+eps)))/(np.mean(s)+eps),0,1)) if len(s)>10 else 0.1
    return SilenceProfile(
        floor_dbfs=floor_db, hum_50hz_db=_hdb(50.0), hum_60hz_db=_hdb(60.0),
        hum_100hz_db=_hdb(100.0), hum_120hz_db=_hdb(120.0),
        noise_sfm=noise_sfm, n_silence_frames=len(sil_frames), valid=True)


# ══════════════════════════════════════════════════════════════════════════════
#  v8.6 — PassMetrics + measure_pass_metrics()
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PassMetrics:
    pass_num:     int   = 0
    eq_residual:  float = 99.0
    crest:        float = 0.0
    crest_delta:  float = 0.0
    lra:          float = 0.0
    lra_error:    float = 99.0
    sibilant_snr: float = 0.0
    lufs:         float = -99.0
    score:        float = 0.0
    passed_gate:  bool  = True


def measure_pass_metrics(wav_path:str, ref_fp:'ReferenceFingerprint',
                         pass_num:int, prev:'Optional[PassMetrics]',
                         skip_s:int=30, sr:int=SR) -> PassMetrics:
    a    = load_audio(wav_path, sr=sr, skip=skip_s, duration=45)
    if len(a) < sr*2: return PassMetrics(pass_num=pass_num)
    b    = third_octave(a); crt=crest_factor(a); lra=lra_estimate(a)
    lufs = measure_lufs(wav_path)
    ref_b= ref_fp.third_oct
    common=[fc for fc in b if fc in ref_b and 80<=fc<=12000]
    if common:
        oa=np.array([b[fc] for fc in common]); ra=np.array([ref_b[fc] for fc in common])
        loff=float(np.mean(ra-oa)); eq_res=float(np.mean(np.abs((ra-oa)-loff)))
    else: eq_res=20.0
    bsnr=compute_band_snr(a)
    sib_snr=float(np.mean([bsnr.get(4000.0,10.0),bsnr.get(8000.0,10.0)]))
    crest_delta=(crt-prev.crest) if prev else 0.0
    m={'lufs':lufs,'rms':float(20*np.log10(np.sqrt(np.mean(a**2))+1e-10)),'crest':crt,'lra':lra}
    sc,_=quality_score(b,ref_fp,m,20000.0)
    return PassMetrics(pass_num=pass_num,eq_residual=round(eq_res,3),
        crest=round(crt,3),crest_delta=round(crest_delta,3),lra=round(lra,3),
        lra_error=round(abs(lra-TARGET['lra']),3),sibilant_snr=round(sib_snr,2),
        lufs=round(lufs,2),score=float(sc),passed_gate=True)


# ══════════════════════════════════════════════════════════════════════════════
#  v8.6 — should_continue() + nr_sibilant_guard() + BestPassTracker
# ══════════════════════════════════════════════════════════════════════════════

_V86_MAX_PASSES = 6

def should_continue(metrics:'List[PassMetrics]', tier:str) -> 'Tuple[bool,str]':
    n=len(metrics)
    if n==0: return True,"no passes yet"
    cur=metrics[-1]; prev=metrics[-2] if n>=2 else None
    if n>=_V86_MAX_PASSES: return False,f"max passes ({_V86_MAX_PASSES}) reached"
    if n>=2 and prev and cur.crest_delta<-0.3 and prev.crest_delta<-0.3:
        return False,"Crest regression (2 consecutive)"
    if prev and cur.eq_residual>prev.eq_residual+0.3:
        return False,f"EQ oscillation ({prev.eq_residual:.2f}→{cur.eq_residual:.2f}dB)"
    if cur.eq_residual<0.5: return False,f"converged (eq={cur.eq_residual:.2f}dB)"
    if prev and cur.score<prev.score-1.5: return False,f"score regression"
    if cur.eq_residual>1.5 and cur.crest_delta>=-0.1: return True,f"eq_residual={cur.eq_residual:.2f}dB"
    if cur.lra_error>0.5 and (prev is None or cur.lra_error<prev.lra_error): return True,"LRA converging"
    if n<3: return True,"standard minimum passes"
    if n==3 and tier in('TIER_DEGRADED','TIER_DAMAGED') and cur.eq_residual>1.0:
        return True,f"DEGRADED/DAMAGED extra pass"
    return False,f"standard {n} passes complete"


def nr_sibilant_guard(pre_snr:float, post_snr:float, current_nr_db:int) -> int:
    drop=pre_snr-post_snr
    if drop>4.0: return 0
    elif drop>2.0: return max(0,current_nr_db-4)
    return current_nr_db


class BestPassTracker:
    def __init__(self):
        self._path=None; self._metrics=None; self._score=-1.0
    @staticmethod
    def _cs(m:'PassMetrics') -> float:
        return (float(np.clip(m.crest/10.25,0,1.2))*0.45
               +float(np.clip(1-m.eq_residual/20,0,1))*0.35
               +float(np.clip(1-m.lra_error/4.19,0,1))*0.20)
    def update(self,wav_path:str,m:'PassMetrics') -> bool:
        cs=self._cs(m)
        if cs>self._score:
            bp=os.path.join(_TMP,'v86_best.wav'); shutil.copy2(wav_path,bp)
            self._path=bp; self._metrics=m; self._score=cs; return True
        return False
    @property
    def best_path(self): return self._path
    @property
    def best_metrics(self): return self._metrics
    @property
    def best_composite_score(self): return self._score


# ══════════════════════════════════════════════════════════════════════════════
#  v8.6 — build_hum_notch() + build_wiener_nr() + build_nr_sfm_v86()
# ══════════════════════════════════════════════════════════════════════════════

def build_hum_notch(silence:'SilenceProfile') -> str:
    if not silence.valid: return ''
    parts=[]
    if silence.hum_50hz_db>15.0:
        parts.append(f'equalizer=f=50:width_type=q:width=0.4:g=-{min(24,int(silence.hum_50hz_db*0.8))}')
    if silence.hum_60hz_db>15.0:
        parts.append(f'equalizer=f=60:width_type=q:width=0.4:g=-{min(24,int(silence.hum_60hz_db*0.8))}')
    if silence.hum_100hz_db>12.0:
        parts.append(f'equalizer=f=100:width_type=q:width=0.6:g=-{min(18,int(silence.hum_100hz_db*0.7))}')
    if silence.hum_120hz_db>12.0:
        parts.append(f'equalizer=f=120:width_type=q:width=0.6:g=-{min(18,int(silence.hum_120hz_db*0.7))}')
    return ','.join(parts)


def build_wiener_nr(silence:'SilenceProfile', tier:str) -> str:
    if (not silence.valid or tier=='TIER_PRISTINE'
            or silence.noise_sfm<0.3 or silence.n_silence_frames<5): return ''
    nf_ceil=int(np.clip(silence.floor_dbfs+3.0,-70,-40))
    max_nr =int(np.clip(abs(nf_ceil),5,15))
    nr_depth=min(max_nr,12 if tier=='TIER_DAMAGED' else 8 if tier=='TIER_DEGRADED' else 5)
    return f'afftdn=nr={nr_depth}:nf={nf_ceil}:tn=1'


def build_nr_sfm_v86(damage:'DamageProfile', silence:'Optional[SilenceProfile]'=None,
                     tier:str='TIER_PRISTINE', hum_notch:str='',
                     ref_nr_floor:float=-76.0) -> 'List[str]':
    """v8.7: ref_nr_floor caps all afftdn nf values. Never push noise below
    ref_fp.silence_floor_db - 3dB (measured 1425H reference floor)."""
    parts=[]
    if hum_notch: parts.append(hum_notch)
    if damage.src_br<96000 and damage.band_snr.get(1000.0,20)<8:
        if damage.has_ringing and damage.rolloff_hz<17000:
            parts.append(f'lowpass=f={int(damage.rolloff_hz*0.97)}:poles=2')
        return parts
    if silence and silence.valid and tier in('TIER_DEGRADED','TIER_DAMAGED'):
        w=build_wiener_nr(silence,tier)
        if w:
            parts.append(w)
            sfm_ratio=damage.sfm/(TARGET['sfm']+1e-6)
            if sfm_ratio>=5.0 and tier=='TIER_DAMAGED': parts.append('afftdn=nr=4:nf=-65:tn=1')
            if damage.has_ringing and damage.rolloff_hz<17000:
                parts.append(f'lowpass=f={int(damage.rolloff_hz*0.97)}:poles=2')
            return parts
    sfm_ratio=damage.sfm/(TARGET['sfm']+1e-6)
    _nf55=max(-55,ref_nr_floor); _nf65=max(-65,ref_nr_floor)
    if sfm_ratio>=5.0:   parts+=[f'afftdn=nr=20:nf={_nf55:.0f}:tn=1',f'afftdn=nr=6:nf={_nf65:.0f}:tn=1']
    elif sfm_ratio>=3.0: parts.append(f'afftdn=nr={int(np.interp(sfm_ratio,[3,5],[12,20]))}:nf={max(-58,ref_nr_floor):.0f}:tn=1')
    elif sfm_ratio>=2.0: parts.append(f'afftdn=nr={int(np.interp(sfm_ratio,[2,3],[6,12]))}:nf={max(-62,ref_nr_floor):.0f}:tn=1')
    elif sfm_ratio>=1.5: parts.append(f'afftdn=nr=4:nf={max(-68,ref_nr_floor):.0f}:tn=1')
    if damage.has_ringing and damage.rolloff_hz<17000:
        parts.append(f'lowpass=f={int(damage.rolloff_hz*0.97)}:poles=2')
    return parts


def build_compand_mds_v86(damage:'DamageProfile', ref_fp:'ReferenceFingerprint',
                           inp_lra:float, tier:str='TIER_PRISTINE'):
    """v8.6: clamp negative crest_delta for DAMAGED tier — prevents BYPASS on collapsed sources"""
    if tier=='TIER_DAMAGED' and (damage.crest-TARGET['crest'])<0:
        dmg2=copy.copy(damage); dmg2.crest=TARGET['crest']
        return build_compand_mds(dmg2,ref_fp,inp_lra)
    return build_compand_mds(damage,ref_fp,inp_lra)



# ══════════════════════════════════════════════════════════════════════════════
#  v8.4 — SOURCE TIER DETECTOR
#  SourceTierProfile + 6 detection functions
#  يُشغَّل مرة واحدة في enhance() بعد DamageProfile وقبل NR
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  v8.7 — EnhancementContext (shared pipeline state)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EnhancementContext:
    """
    v8.7: single shared state passed to all pipeline modules.
    Replaces scattered per-module variables that caused NR/EQ coordination bugs.
    """
    ref_model:          'ReferenceFingerprint' = field(default_factory=lambda: ReferenceFingerprint())
    source_tier:        str                    = 'TIER_PRISTINE'
    input_cutoff_hz:    float                  = 20000.0
    noise_type:         str                    = 'none'
    clip_tier:          str                    = 'none'
    achievable_targets: Dict                   = field(default_factory=dict)
    mds_weights:        Dict                   = field(default_factory=dict)
    silence_profile:    'Optional[SilenceProfile]' = None
    # v8.7
    post_nr_spectrum:   Dict[float, float]     = field(default_factory=dict)
    smear_score:        float                  = 0.0
    smear_desc:         str                    = ''
    bsr_chain:          str                    = ''
    bsr_applied:        bool                   = False
    ref_nr_floor:       float                  = -76.0
    skip_s:             int                    = 30
    dur_s:              int                    = 45


@dataclass
class SourceTierProfile:
    """
    نتيجة تصنيف جودة المصدر — تُحدَّد قبل أي معالجة.
    تُمرَّر لكل وحدة في الـ pipeline لتضبط حدود التدخل.
    """
    # ── نتائج القياس ──────────────────────────────────────────────────
    tier:             str   = 'TIER_PRISTINE'
    input_cutoff_hz:  float = 20000.0   # تردد قطع الكودك المُقاس
    noise_type:       str   = 'none'    # none|hiss|hum_50hz|hum_60hz|broadband|hiss+hum
    clip_tier:        str   = 'none'    # none|mild|moderate|severe
    clip_ratio:       float = 0.0       # نسبة العينات المقطوعة 0–1
    hum_freq_hz:      float = 0.0       # 50.0 أو 60.0 إذا وُجد hum
    sfm_silence:      float = 0.0       # SFM في مقاطع الصمت
    snr_effective:    float = 30.0      # SNR الفعلي
    # ── معاملات التوجيه — تُشتق من الـ tier ──────────────────────────
    bias_cutoff_hz:   float = 20000.0   # لا BIAS g>0 فوق هذا التردد
    eq_ramp_scale:    float = 1.0       # مضاعف على scale في adaptive EQ
    nr_mandatory:     bool  = False     # أجبر NR حتى لو SFM يقول لا
    lra_expand_gate:  bool  = True      # اسمح بتوسيع LRA في Pass 3
    achievable_crest: float = 10.25     # سقف Crest الفيزيائي
    achievable_lra:   float = 4.19      # هدف LRA القابل للتحقيق
    achievable_lufs:  float = -6.29     # هدف LUFS القابل للتحقيق


def detect_codec_cutoff(inp_b: Dict[float, float]) -> float:
    """
    يمسح CENTERS_31 من 20kHz نزولاً.
    أول نطاق فيه طاقة > (noise_floor_p10 + 6dB) = تردد القطع.

    الفيزياء: ضوضاء التكميم طيفها شبه مسطح تحت الإشارة.
    فوق تردد القطع: إشارة تسقط تحت ضوضاء التكميم.
    Bypass: inp_b فارغة → 20000.0
    """
    if not inp_b:
        return 20000.0
    all_vals = sorted(inp_b.values())
    noise_floor = float(np.percentile(all_vals, 10)) if len(all_vals) >= 4 else -70.0
    threshold = noise_floor + 6.0
    for fc in sorted(inp_b.keys(), reverse=True):
        if inp_b[fc] > threshold:
            return float(fc)
    return float(min(inp_b.keys(), default=20000.0))


def detect_noise_type(audio: 'np.ndarray',
                      sr: int = SR) -> Tuple[str, float, float]:
    """
    يحدد نوع الضوضاء من مقاطع الصمت (إطارات 200ms).

    الخوارزمية:
      1. إطارات الصمت: (overall_rms-18dB) > frame_rms > -62dBFS
      2. SFM على الصمت المُدمج — SFM>0.65 = broadband noise
      3. طاقة 50Hz / 60Hz مقابل الجيران +25Hz — +15dB = hum

    Bypass: audio قصير جداً (<3 إطارات صمت) → ('unknown', 0.0, 0.0)
    Returns: (noise_type, sfm_silence, hum_freq_hz)
    """
    frame_n = int(0.2 * sr)
    if len(audio) < frame_n * 3:
        return ('unknown', 0.0, 0.0)
    overall_rms_db = rms_db(audio)
    silence_thresh = overall_rms_db - 18.0
    silence_floor  = -62.0
    frames = [audio[i:i+frame_n]
              for i in range(0, len(audio) - frame_n, frame_n)]
    silence_frames = [f for f in frames
                      if silence_floor < rms_db(f) < silence_thresh]
    if len(silence_frames) < 3:
        return ('unknown', 0.0, 0.0)
    silence_audio = np.concatenate(silence_frames)
    sfm_sil = compute_sfm(silence_audio, sr, f_lo=200.0, f_hi=8000.0)
    hum_freq = 0.0
    N_sil = len(silence_audio)
    spec_sil = np.abs(rfft(silence_audio)) ** 2
    freqs_sil = rfftfreq(N_sil, 1.0 / sr)
    def _band_e(fc: float, bw: float = 3.0) -> float:
        mask = (freqs_sil >= fc - bw) & (freqs_sil <= fc + bw)
        return float(np.mean(spec_sil[mask])) if mask.sum() > 0 else 1e-30
    for test_hz in [50.0, 60.0]:
        ratio_db = 10 * np.log10(
            _band_e(test_hz) /
            (np.mean([_band_e(test_hz-25.0), _band_e(test_hz+25.0)]) + 1e-30)
            + 1e-30
        )
        if ratio_db > 15.0:
            hum_freq = test_hz
            break
    has_hiss = sfm_sil > 0.65
    has_hum  = hum_freq > 0.0
    if has_hiss and has_hum:   noise_type = 'hiss+hum'
    elif has_hiss:             noise_type = 'hiss' if sfm_sil < 0.85 else 'broadband'
    elif has_hum:              noise_type = f'hum_{int(hum_freq)}hz'
    else:                      noise_type = 'none'
    return (noise_type, float(sfm_sil), float(hum_freq))


def detect_clip_tier_v84(audio: 'np.ndarray') -> Tuple[str, float]:
    """يُصنّف مستوى القطع — wrapper على count_clips()."""
    n_clips = count_clips(audio, thr=0.99)
    ratio = n_clips / max(len(audio), 1)
    if ratio < 0.001:   tier = 'none'
    elif ratio < 0.02:  tier = 'mild'
    elif ratio < 0.20:  tier = 'moderate'
    else:               tier = 'severe'
    return tier, float(ratio)


def _classify_source_tier(src_br: int, cutoff_hz: float,
                          snr_db: float, noise_type: str) -> str:
    """
    تصنيف فئة المصدر — أول قاعدة تنطبق تُحدد الفئة.

    TIER_PRISTINE:   128kbps+ AND cutoff>14kHz AND SNR>25dB AND noise=none
    TIER_COMPRESSED: 64kbps+  AND cutoff>10kHz AND SNR>15dB
    TIER_DEGRADED:   32kbps+  AND cutoff>7kHz  AND SNR>8dB
    TIER_DAMAGED:    كل ما تبقى
    """
    if (src_br >= 128_000 and cutoff_hz > 14_000.0
            and snr_db > 25.0 and noise_type == 'none'):
        return 'TIER_PRISTINE'
    if src_br >= 64_000 and cutoff_hz > 10_000.0 and snr_db > 15.0:
        return 'TIER_COMPRESSED'
    if src_br >= 32_000 and cutoff_hz > 7_000.0 and snr_db > 8.0:
        return 'TIER_DEGRADED'
    return 'TIER_DAMAGED'


def _build_routing_params(tier: str, cutoff_hz: float,
                          noise_type: str, inp_lra: float,
                          ref_lra_clip: float) -> dict:
    """يُنتج معاملات التوجيه من الـ tier — مُنفصل للاختبار."""
    lra_deficit = ref_lra_clip - inp_lra
    if tier == 'TIER_PRISTINE':
        return dict(
            bias_cutoff_hz=20_000.0, eq_ramp_scale=1.0,
            nr_mandatory=False,      lra_expand_gate=True,
            achievable_crest=10.25,  achievable_lra=4.19,  achievable_lufs=-6.29,
        )
    if tier == 'TIER_COMPRESSED':
        return dict(
            bias_cutoff_hz=cutoff_hz * 0.90, eq_ramp_scale=0.70,
            nr_mandatory=(noise_type != 'none'), lra_expand_gate=True,
            achievable_crest=9.5,  achievable_lra=4.0,  achievable_lufs=-6.29,
        )
    if tier == 'TIER_DEGRADED':
        return dict(
            bias_cutoff_hz=min(8_000.0, cutoff_hz * 0.85), eq_ramp_scale=0.40,
            nr_mandatory=True,  lra_expand_gate=(lra_deficit > 0.8),
            achievable_crest=8.5,  achievable_lra=3.6,  achievable_lufs=-6.5,
        )
    # TIER_DAMAGED
    return dict(
        bias_cutoff_hz=4_000.0, eq_ramp_scale=0.20,
        nr_mandatory=True,      lra_expand_gate=False,
        achievable_crest=7.5,   achievable_lra=3.2,   achievable_lufs=-7.0,
    )


def build_source_tier_profile(audio: 'np.ndarray',
                              inp_b: Dict[float, float],
                              src_br: int,
                              snr_db: float,
                              inp_lra: float,
                              ref_lra_clip: float,
                              sr: int = SR) -> SourceTierProfile:
    """
    الدالة الرئيسية — تُشغّل جميع المستشعرات وتُجمّع SourceTierProfile.
    يُستدعى مرة واحدة في enhance() بعد DamageProfile وقبل NR.
    """
    cutoff_hz = detect_codec_cutoff(inp_b)
    noise_type, sfm_sil, hum_freq = detect_noise_type(audio, sr)
    effective_noise = noise_type if noise_type != 'unknown' else 'none'
    clip_tier, clip_ratio = detect_clip_tier_v84(audio)
    tier    = _classify_source_tier(src_br, cutoff_hz, snr_db, effective_noise)
    routing = _build_routing_params(tier, cutoff_hz, effective_noise,
                                    inp_lra, ref_lra_clip)
    return SourceTierProfile(
        tier=tier, input_cutoff_hz=cutoff_hz,
        noise_type=noise_type, clip_tier=clip_tier, clip_ratio=clip_ratio,
        hum_freq_hz=hum_freq, sfm_silence=sfm_sil, snr_effective=snr_db,
        **routing,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO I/O
# ══════════════════════════════════════════════════════════════════════════════

def _safe(path:str) -> Tuple[str,Optional[str]]:
    """v8.1 PATCH #3: use _TMP (platform-aware) instead of hardcoded /tmp/"""
    try: path.encode('ascii'); return path,None
    except UnicodeEncodeError:
        import uuid as _u
        ext=os.path.splitext(path)[1] or '.mp3'
        tmp=os.path.join(_TMP, f'v81_safe_{_u.uuid4().hex[:8]}{ext}')
        try:
            shutil.copy2(path,tmp)
        except OSError:
            # last resort: write beside the output in cwd
            tmp=os.path.join(os.getcwd(), f'v81_safe_{_u.uuid4().hex[:8]}{ext}')
            shutil.copy2(path,tmp)
        return tmp,tmp

def load_audio(path:str,sr:int=SR,mono:bool=True,
               skip:int=0,duration:Optional[int]=None) -> 'np.ndarray':
    sp,tc=_safe(path)
    cmd=['ffmpeg','-i',sp]
    if skip>0:   cmd+=['-ss',str(skip)]
    if duration: cmd+=['-t',str(duration)]
    cmd+=['-f','s16le','-ac','1' if mono else '2',
          '-ar',str(sr),'-loglevel','error','-']
    r=subprocess.run(cmd,capture_output=True)
    if tc:
        try: os.remove(tc)
        except: pass
    if not r.stdout: raise RuntimeError(f'فشل تحميل: {path}')
    return np.frombuffer(r.stdout,np.int16).astype(np.float32)/32768.0

def probe(path:str) -> Dict:
    sp,tc=_safe(path)
    r=subprocess.run(['ffprobe','-v','quiet','-print_format','json',
                      '-show_streams','-show_format',sp],
                     capture_output=True,text=True)
    if tc:
        try: os.remove(tc)
        except: pass
    return json.loads(r.stdout) if r.returncode==0 else {}

def measure_lufs(path:str) -> float:
    sp,tc=_safe(path)
    r=subprocess.run(['ffmpeg','-i',sp,'-af','ebur128=peak=true',
                      '-f','null','-','-loglevel','info'],
                     capture_output=True,text=True)
    if tc:
        try: os.remove(tc)
        except: pass
    for line in r.stderr.split('\n'):
        s=line.strip()
        if s.startswith('I:') and 'LUFS' in s and 'LRA' not in s:
            try: return float(s.split('I:')[1].strip().split()[0])
            except: pass
    return -99.0

# ══════════════════════════════════════════════════════════════════════════════
#  SIGNAL METRICS
# ══════════════════════════════════════════════════════════════════════════════

def rms_db(a:'np.ndarray') -> float:
    return float(20*np.log10(np.sqrt(np.mean(a**2))+1e-10))

def peak_db(a:'np.ndarray') -> float:
    return float(20*np.log10(np.max(np.abs(a))+1e-10))

def crest_factor(a:'np.ndarray') -> float:
    return float(peak_db(a)-rms_db(a))

def lra_estimate(a:'np.ndarray',sr:int=SR) -> float:
    n=int(0.4*sr); step=n//2
    lvls=np.array([20*np.log10(np.sqrt(np.mean(a[i:i+n]**2))+1e-10)
                   for i in range(0,len(a)-n,step)])
    if len(lvls)<2: return 0.0
    active=lvls[lvls>np.max(lvls)-30]
    return float(np.percentile(active,95)-np.percentile(active,10)) if len(active)>=2 else 0.0

def snr_estimate(a:'np.ndarray',sr:int=SR) -> float:
    n=int(0.1*sr)
    blocks=np.array([np.sqrt(np.mean(a[i:i+n]**2)) for i in range(0,len(a)-n,n)])
    if len(blocks)<4: return 30.0
    return float(20*np.log10(np.percentile(blocks,85)/(np.percentile(blocks,3)+1e-10)))

def count_clips(a:'np.ndarray',thr:float=0.99) -> int:
    return int(np.sum(np.abs(a)>=thr))

def declip(audio:'np.ndarray',thr:float=0.98) -> Tuple['np.ndarray',int]:
    clipped=np.abs(audio)>=thr; nc=int(np.sum(clipped))
    if nc==0: return audio,0
    out=audio.copy(); n=len(audio)
    diff=np.diff(clipped.astype(int))
    starts=np.where(diff==1)[0]+1; ends=np.where(diff==-1)[0]+1
    if clipped[0]:  starts=np.insert(starts,0,0)
    if clipped[-1]: ends=np.append(ends,n)
    for s,e in zip(starts,ends):
        ctx=40; pre=np.arange(max(0,s-ctx),s); post=np.arange(e,min(n,e+ctx))
        good=np.concatenate([pre,post])
        if len(good)<4: continue
        try:
            cs=CubicSpline(good,audio[good],extrapolate=True)
            out[np.arange(s,e)]=cs(np.arange(s,e))
        except: pass
    return out,nc

# ══════════════════════════════════════════════════════════════════════════════
#  SPECTRAL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def third_octave(audio:'np.ndarray',sr:int=SR,
                 chunk_sec:int=45,a_weighted:bool=False) -> Dict[float,float]:
    chunk=audio[:sr*chunk_sec] if len(audio)>sr*chunk_sec else audio
    N=len(chunk); spec=np.abs(rfft(chunk)); freqs=rfftfreq(N,1.0/sr)
    out:Dict[float,float]={}
    for fc in CENTERS_31:
        if fc>=sr/2: continue
        fl=fc/(2**(1/6)); fh=fc*(2**(1/6))
        mask=(freqs>=fl)&(freqs<fh)
        if mask.sum()>0:
            v=float(20*np.log10(np.mean(spec[mask])+1e-10))
            if a_weighted and fc in A_WEIGHT: v+=A_WEIGHT[fc]
            out[fc]=v
    return out

def hf_status(bands:Dict[float,float]) -> str:
    hfk=[f for f in bands if f>=8000]
    if not hfk: return 'absent'
    avg=float(np.mean([bands[f] for f in hfk]))
    return 'good' if avg>10 else 'weak' if avg>-5 else 'absent'

def detect_hf_rolloff(bands:Dict[float,float],drop:float=12.0) -> float:
    fs=sorted([f for f in bands if 1600<=f<=20000])
    if not fs: return 20000.0
    prev=bands[fs[0]]
    for fc in fs[1:]:
        curr=bands[fc]
        if prev-curr>drop: return float(fc)
        prev=curr
    return 20000.0

def spectral_tilt(bands:Dict[float,float],lo:float=100.0,hi:float=10000.0) -> float:
    fc_arr=np.array([fc for fc in CENTERS_31 if lo<=fc<=hi and fc in bands],dtype=float)
    if len(fc_arr)<3: return 0.0
    return float(np.polyfit(np.log2(fc_arr/1000.0),
                            np.array([bands[fc] for fc in fc_arr]),1)[0])

def warmth_tilt(bands:Dict[float,float]) -> float:
    return spectral_tilt(bands,200.0,2000.0)

def merge_eq(nodes:List[Tuple],gap:float=50.0) -> List[Tuple]:
    if not nodes: return nodes
    nodes=sorted(nodes,key=lambda x:x[0]); merged=[list(nodes[0])]
    for f0,g,Q in nodes[1:]:
        pf,pg,pq=merged[-1]
        if abs(f0-pf)<gap:
            total=float(np.clip(pg+g,-16,16))
            avg_f=(pf*abs(pg)+f0*abs(g))/(abs(pg)+abs(g)+1e-6)
            merged[-1]=[round(avg_f,0),round(total,2),round((pq+Q)/2,2)]
        else: merged.append([f0,g,Q])
    return [tuple(x) for x in merged]

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1a — SPECTRAL FLATNESS MEASURE (SFM)
# ══════════════════════════════════════════════════════════════════════════════

def compute_sfm(audio:'np.ndarray',sr:int=SR,
                f_lo:float=100.0,f_hi:float=8000.0) -> float:
    """Wiener entropy — مقياس نظافة الطيف | REF 1425H: 0.044"""
    chunk=audio[:sr*30] if len(audio)>sr*30 else audio
    N=len(chunk); spec=np.abs(rfft(chunk))**2; freqs=rfftfreq(N,1.0/sr)
    mask=(freqs>=f_lo)&(freqs<=f_hi)
    s=spec[mask]
    if len(s)<10: return 0.1
    eps=1e-10
    geo=float(np.exp(np.mean(np.log(s+eps))))
    arith=float(np.mean(s))
    return float(np.clip(geo/(arith+eps),0.0,1.0))

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1b — DYNAMIC RANGE SCORE
# ══════════════════════════════════════════════════════════════════════════════

def compute_dynamic_range(audio:'np.ndarray',sr:int=SR) -> float:
    """نطاق الديناميك الفعلي (20ms frames) | REF: 7.9dB"""
    n=int(0.020*sr)
    frames=np.array([float(np.sqrt(np.mean(audio[i:i+n]**2)))
                     for i in range(0,len(audio)-n,n)])
    if len(frames)<10: return 8.0
    frames_db=20*np.log10(frames+1e-10)
    return float(np.percentile(frames_db,95)-np.percentile(frames_db,5))

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1c — SPECTRAL SHAPE DISTANCE FROM REFERENCE
# ══════════════════════════════════════════════════════════════════════════════

def compute_spectral_distance(inp_b:Dict,ref_fp:ReferenceFingerprint,
                               hf_rolloff:float=20000.0) -> float:
    """المسافة الطيفية الحقيقية من المرجع بعد level normalization"""
    ref_b=ref_fp.third_oct
    ceil=min(10000.0,hf_rolloff*0.9)
    common=[fc for fc in inp_b if fc in ref_b and 80<=fc<=ceil]
    if len(common)<4: return 20.0
    out_arr=np.array([inp_b[fc] for fc in common])
    ref_arr=np.array([ref_b[fc] for fc in common])
    loff=float(np.mean(ref_arr-out_arr))
    shape_diffs=np.abs((ref_arr-out_arr)-loff)
    aw=np.array([max(0.2,1+A_WEIGHT.get(fc,0)/10) for fc in common])
    return float(np.sum(aw*shape_diffs)/np.sum(aw))

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1d — CODEC DAMAGE FINGERPRINT (Per-Band SNR)
# ══════════════════════════════════════════════════════════════════════════════

def compute_band_snr(audio:'np.ndarray',sr:int=SR) -> Dict[float,float]:
    """SNR لكل Bark band — يُحدد أين تحتاج NR"""
    N=len(audio); spec=np.abs(rfft(audio))**2; freqs=rfftfreq(N,1.0/sr)
    band_snr={}
    for fc in [125,250,500,1000,2000,4000,8000]:
        fl=fc*0.7; fh=fc*1.4
        mask=(freqs>=fl)&(freqs<fh)
        if mask.sum()<4: continue
        s=spec[mask]
        snr=float(10*np.log10(np.percentile(s,85)/(np.percentile(s,5)+1e-30)+1e-10))
        band_snr[float(fc)]=snr
    return band_snr

# ══════════════════════════════════════════════════════════════════════════════
#  MULTI-METRIC DAMAGE SCORE (MDS)
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  v8.5 — TIER-ADJUSTED SCORING (TierAdjustedScoring)
#  Per-tier MDS weights for compute_mds() and achievable target dicts
#  for quality_score().  Replaces the ad-hoc 64K_FLOOR hack.
# ══════════════════════════════════════════════════════════════════════════════

# TIER_DAMAGED: HF is irrelevant (codec wiped it); SNR/SFM dominate.
# TIER_PRISTINE: balanced, as before v8.5.
_V85_MDS_WEIGHTS: Dict[str, Dict[str, float]] = {
    'TIER_PRISTINE':   {'snr': 0.25, 'sfm': 0.25, 'spec': 0.20,
                        'hf':  0.15, 'dr':  0.10, 'br':   0.05},
    'TIER_COMPRESSED': {'snr': 0.30, 'sfm': 0.25, 'spec': 0.18,
                        'hf':  0.07, 'dr':  0.12, 'br':   0.08},
    'TIER_DEGRADED':   {'snr': 0.35, 'sfm': 0.28, 'spec': 0.15,
                        'hf':  0.02, 'dr':  0.12, 'br':   0.08},
    'TIER_DAMAGED':    {'snr': 0.40, 'sfm': 0.30, 'spec': 0.10,
                        'hf':  0.00, 'dr':  0.12, 'br':   0.08},
}


def _compute_achievable_targets(tier: str, input_cutoff_hz: float) -> Dict:
    """
    Per-tier achievable target dict.

    TIER_PRISTINE:   full 1425H targets unchanged.
    TIER_COMPRESSED: Crest ceiling 9.8LU, LRA 4.0LU (64kbps+ codec AGC).
    TIER_DEGRADED:   Crest linear from 7.5 to 9.0 LU based on measured
                     codec cutoff.  LUFS -6.5 (noisy floor lifts noise).
    TIER_DAMAGED:    Crest 7.0LU, LRA 3.2LU, LUFS -7.0 (severe damage).

    PHYSICS JUSTIFICATION (Crest ceiling):
      A 64kbps MP3 codec applies AGC and quantization noise that floors
      the noise floor by ~15dBFS relative to peaks.  The measurable effect
      is Crest depression: a source with Crest=12LU will emerge from 64kbps
      encode at ~9.0-9.5LU.  Scoring the output against a 10.25LU target
      penalises the engine for a physical limit, not a processing error.
    """
    if tier == 'TIER_PRISTINE':
        return dict(TARGET)
    if tier == 'TIER_COMPRESSED':
        return {**TARGET, 'crest': 9.8, 'lra': 4.0}
    if tier == 'TIER_DEGRADED':
        # Linear: 7.5LU at cutoff=0Hz → 9.0LU at cutoff=10500Hz
        crest_ceil = float(np.clip(7.5 + (input_cutoff_hz / 10500.0) * 1.5, 7.5, 9.0))
        return {**TARGET, 'crest': crest_ceil, 'lra': 3.6, 'lufs': -6.5}
    # TIER_DAMAGED
    return {**TARGET, 'crest': 7.0, 'lra': 3.2, 'lufs': -7.0}


def compute_mds(snr:float,sfm:float,dr:float,hf_deficit:float,
                spectral_dist:float,src_br:int,
                ref_sfm:float=TARGET['sfm'],
                ref_dr:float=TARGET['dr'],
                source_tier:str='TIER_PRISTINE') -> float:
    """
    Multi-Metric Damage Score: 0=مثالي | 100=أسوأ حالة
    أوزان: SNR 25% | SFM 25% | Spectral Distance 20% | HF 15% | DR 10% | BR 5%
    """
    snr_score  =float(np.clip((30.0-snr)/30.0,0,1))*100
    sfm_ratio  =sfm/(ref_sfm+1e-6)
    sfm_score  =float(np.clip((sfm_ratio-1.0)/5.0,0,1))*100
    spec_score =float(np.clip(spectral_dist/15.0,0,1))*100
    hf_score   =float(np.clip(hf_deficit/30.0,0,1))*100
    dr_excess  =max(0.0,dr-ref_dr)
    dr_score   =float(np.clip(dr_excess/8.0,0,1))*100
    br_score   =float(np.clip((128000-src_br)/100000,0,1))*100
    # v8.5: tier-specific weights — TIER_DAMAGED weights SNR/SFM heavily, HF=0
    w = _V85_MDS_WEIGHTS.get(source_tier, _V85_MDS_WEIGHTS['TIER_PRISTINE'])
    mds = (snr_score * w['snr'] + sfm_score * w['sfm'] + spec_score * w['spec'] +
           hf_score  * w['hf']  + dr_score  * w['dr']  + br_score   * w['br'])
    return float(np.clip(mds, 0, 100))

def mds_to_label(mds:float) -> str:
    if mds>=75: return 'EXTREME'
    if mds>=55: return 'VERY_POOR'
    if mds>=35: return 'POOR'
    if mds>=18: return 'FAIR'
    return 'GOOD'

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2a — SFM-ADAPTIVE NR
# ══════════════════════════════════════════════════════════════════════════════

def build_nr_sfm(damage:DamageProfile) -> List[str]:
    """NR intensity = f(SFM ratio) — محافَظ عليه من v7.6"""
    parts:List[str]=[]
    if damage.src_br < 96000 and damage.band_snr.get(1000.0,20) < 8:
        if damage.has_ringing and damage.rolloff_hz < 17000:
            parts.append(f'lowpass=f={int(damage.rolloff_hz*0.97)}:poles=2')
        return parts
    sfm_ratio=damage.sfm/(TARGET['sfm']+1e-6)
    if sfm_ratio >= 5.0:
        parts.append('afftdn=nr=20:nf=-55:tn=1')
        parts.append('afftdn=nr=6:nf=-65:tn=1')
    elif sfm_ratio >= 3.0:
        nr=int(np.interp(sfm_ratio,[3,5],[12,20]))
        parts.append(f'afftdn=nr={nr}:nf=-58:tn=1')
    elif sfm_ratio >= 2.0:
        nr=int(np.interp(sfm_ratio,[2,3],[6,12]))
        parts.append(f'afftdn=nr={nr}:nf=-62:tn=1')
    elif sfm_ratio >= 1.5:
        parts.append('afftdn=nr=4:nf=-68:tn=1')
    if damage.has_ringing and damage.rolloff_hz < 17000:
        parts.append(f'lowpass=f={int(damage.rolloff_hz*0.97)}:poles=2')
    return parts

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2b — v8 BUG #4 FIX — DR-CALIBRATED COMPAND (LRA delta صحيح)
# ══════════════════════════════════════════════════════════════════════════════

def build_compand_mds(damage:DamageProfile,
                      ref_fp:ReferenceFingerprint,
                      inp_lra:float) -> Tuple[str,float,str,float]:
    """
    v8 FIX #4: compand selection باستخدام LRA الفعلي بدل DR
    v7.6 كان: lra_delta = damage.dr - TARGET['dr']  ← خطأ نوع!
    v8:       lra_delta = inp_lra - ref_fp.lra_clip  ← صحيح
    """
    crest_delta = damage.crest - TARGET['crest']
    # v8 FIX: LRA excess الحقيقي مقارنة بالـ clip reference
    lra_delta   = max(0.0, inp_lra - ref_fp.lra_clip)
    # MDS contribution — مقلّص من 3.0 إلى 2.0 لتجنب overweighting
    mds_contrib = damage.mds / 100.0 * 2.0

    score = crest_delta * 0.72 + lra_delta * 0.20 + mds_contrib

    if score >= 11:
        return ("-90/-68|-45/-20|-28/-9|-14/-4.5|-7/-2.0|-3/-0.6|0/-0.1",
                2.5,'EXTREME',2.0)
    elif score >= 6.5:
        return ("-90/-72|-42/-21|-26/-10.5|-13/-5.2|-6/-2.4|-2.5/-0.8|-0.5/-0.3|0/-0.1",
                3.2,'HEAVY',1.8)
    elif score >= 3.5:
        return ("-90/-78|-40/-25|-22/-12.5|-12/-6.8|-6/-3.5|-2.5/-1.6|-0.8/-0.5|0/-0.2",
                2.5,'MEDIUM',1.4)
    elif score >= 1.5:
        return ("-90/-85|-40/-36|-20/-17|-10/-8.2|-5/-4.1|-2/-1.6|-0.5/-0.4|0/-0.3",
                1.2,'LIGHT',0.9)
    elif score >= 0.5:
        return ("-90/-89|-40/-39|-20/-19.5|-10/-9.8|-4/-3.9|-1/-0.95|0/-0.3",
                0.4,'MINIMAL',0.4)
    else:
        return ("-90/-90|-20/-20|-3/-3|0/0",0.0,'BYPASS',0.0)

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2c — v8 BUG #1 FIX — CORRECTED SPECTRAL BIAS
# ══════════════════════════════════════════════════════════════════════════════

def build_bias_filter(hf_rolloff:float=20000.0,
                      bias_cutoff_hz:float=20000.0) -> str:
    """
    v8 FIX #1: SPECTRAL_BIAS_V8 باتفاقية صحيحة موحدة
    الصيغة: g = -bias * BIAS_SCALE
    bias سالب → g موجب (boost) | bias موجب → g سالب (cut)

    v8.4:  bias_cutoff_hz از SourceTierProfile (tier codec ceiling)
    v8.45: ref_codec_cutoff_hz من DeepReferenceModel (ref file ceiling)
      فلا نُعزز تردداً لا يحتوي المرجع نفسه على محتوى حقيقي فيه.
      (FORENSIC: الـ 320kbps refs عندها cutoff ≈14kHz وليس 20kHz)
    """
    effective_boost_ceil = min(hf_rolloff * 0.9, bias_cutoff_hz)
    parts=[]
    for fc,bias_db in SPECTRAL_BIAS_V8.items():
        g=round(-bias_db * BIAS_SCALE, 2)
        if abs(g) < 0.20: continue
        if g > 0 and fc > effective_boost_ceil: continue  # v8.4: لا boost فوق سقف الكودك
        if fc > hf_rolloff * 0.9: continue                # v8.2: حد hf_rolloff للـ cut
        Q=0.65 if abs(g)>1.5 else 0.90
        parts.append(f'equalizer=f={fc}:width_type=q:width={Q}:g={g}')
    return ','.join(parts)

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2d — SPECTRAL DISTANCE EQ (Perceptual Optimizer)
# ══════════════════════════════════════════════════════════════════════════════

def optimize_eq(new_b:Dict,ref_fp:ReferenceFingerprint,
                n_nodes:int=12,max_db:float=6.0,
                shape_only:bool=False,hf_rolloff:float=20000.0) -> List[Tuple]:
    """scipy optimizer — يُصحح المسافة الطيفية الحقيقية | محافَظ عليه من v7.6"""
    ref_b=ref_fp.third_oct
    ceil=min(12000.0,hf_rolloff*0.92)
    common=sorted([fc for fc in new_b if fc in ref_b and 63<=fc<=ceil])
    if len(common)<4: return []

    fc_arr=np.array(common,dtype=float)
    new_arr=np.array([new_b[fc] for fc in common])
    ref_arr=np.array([ref_b[fc] for fc in common])
    loff=float(np.mean(ref_arr-new_arr))
    target=(ref_arr-new_arr)-loff
    if shape_only: target=target-float(np.mean(target))

    def baw(fc:float) -> float:
        bw=2.0 if 500<=fc<=4000 else 1.6 if 200<=fc<500 else 1.4 if 4000<fc<=8000 else 0.9
        return bw*max(0.3,1+A_WEIGHT.get(fc,0)/10)
    aw=np.array([baw(fc) for fc in common])
    init_f=np.logspace(np.log10(63),np.log10(ceil),n_nodes)

    def resp(fa,p):
        r=np.zeros(len(fa))
        for i in range(n_nodes):
            f0=abs(p[i*3])+1e-6; g=p[i*3+1]; Q=max(0.3,abs(p[i*3+2]))
            rat=fa/f0; r+=g/(1+Q**2*(rat-1.0/(rat+1e-9))**2)
        return r

    def obj(p):
        e=np.mean(aw*(resp(fc_arr,p)-target)**2)
        gs=[p[i*3+1] for i in range(n_nodes)]
        sm=sum(0.012*(gs[i+1]-gs[i])**2 for i in range(len(gs)-1))
        mg=sum(0.002*g**2 for g in gs)
        return e+sm+mg

    ig=np.interp(np.log10(init_f),np.log10(fc_arr),target)
    x0=[]
    for f,g in zip(init_f,ig):
        x0.extend([float(np.clip(f,63,ceil)),float(np.clip(g,-max_db,max_db)),1.0])

    res=minimize(obj,x0,method='L-BFGS-B',
                 bounds=[(63,ceil),(-max_db,max_db),(0.3,4.5)]*n_nodes,
                 options={'maxiter':500,'ftol':1e-10,'gtol':1e-9})
    nodes=[]
    for i in range(n_nodes):
        f0=abs(res.x[i*3]); g=res.x[i*3+1]; Q=max(0.3,abs(res.x[i*3+2]))
        if shape_only and g<0 and 400<=f0<=1600: g=max(g,-2.0)
        if abs(g)>=0.35: nodes.append((round(f0,0),round(g,2),round(Q,2)))
    return sorted(nodes,key=lambda x:x[0])

# ══════════════════════════════════════════════════════════════════════════════
#  WARMTH CORRECTION (Crest-Aware — محافَظ عليه من v7.55/v7.6)
# ══════════════════════════════════════════════════════════════════════════════

def build_warmth_nodes(inp_b:Dict,ref_fp:ReferenceFingerprint,
                       hf_rolloff:float=20000.0,post_compand:bool=False,
                       current_crest:float=99.0) -> List[Tuple]:
    tfc=np.array([fc for fc in CENTERS_31 if 200<=fc<=2000
                   and fc in inp_b and fc<hf_rolloff],dtype=float)
    if len(tfc)<3: return []
    tdb=np.array([inp_b[fc] for fc in tfc])
    new_tilt=float(np.polyfit(np.log2(tfc/1000.0),tdb,1)[0])
    tilt_diff=ref_fp.warmth_ratio-new_tilt
    threshold=1.5 if not post_compand else 2.5
    if abs(tilt_diff)<threshold: return []

    # حارس Crest (من v7.55 — محافَظ عليه)
    if current_crest-TARGET['crest']<-1.0: return []

    max_adj=min(3.0,2.0+(current_crest-TARGET['crest'])*0.5) if not post_compand else 1.2
    scale=0.35 if not post_compand else 0.20
    nodes=[]
    adj=float(np.clip(tilt_diff*scale,-max_adj,max_adj))
    if abs(adj)>=0.4: nodes.append((200.0,round(adj,2),0.55))
    madj=float(np.clip(-tilt_diff*0.12,-1.5,1.5))
    if abs(madj)>=0.3: nodes.append((1000.0,round(madj,2),0.80))
    return nodes

# ══════════════════════════════════════════════════════════════════════════════
#  SPECTRAL CORRECTION (Conservative — محافَظ عليه من v7.6)
# ══════════════════════════════════════════════════════════════════════════════

def spectral_correction(out_b:Dict,ref_fp:ReferenceFingerprint,
                        hf_rolloff:float=20000.0,max_db:float=3.0,
                        pass_num:int=2,current_crest:float=99.0) -> List[Tuple]:
    ref_b=ref_fp.third_oct
    ceil=min(10000.0,hf_rolloff*0.9)
    common=sorted([fc for fc in out_b if fc in ref_b and 80<=fc<=ceil])
    if len(common)<4: return []

    out_arr=np.array([out_b[fc] for fc in common])
    ref_arr=np.array([ref_b[fc] for fc in common])
    loff=float(np.mean(ref_arr-out_arr))
    shape=(ref_arr-out_arr)-loff
    avg_err=float(np.mean(np.abs(shape)))

    base=0.58 if avg_err>4.0 else 0.48 if avg_err>2.0 else 0.35
    pm={2:1.00,3:0.70,4:0.45}.get(pass_num,1.00)
    scale=base*pm

    aw=np.array([max(0.3,1+A_WEIGHT.get(fc,0)/10) for fc in common])

    tfc=np.array([fc for fc in common if 200<=fc<=2000],dtype=float)
    warmth_ok=False
    if len(tfc)>=3:
        tdb=np.array([out_b[fc] for fc in tfc])
        out_tw=float(np.polyfit(np.log2(tfc/1000.0),tdb,1)[0])
        warmth_ok=abs(out_tw-ref_fp.warmth_ratio)<3.0

    crest_headroom=current_crest-TARGET['crest']

    nodes:List[Tuple]=[]; prev_g=0.0
    for i,fc in enumerate(common):
        raw_g=float(shape[i])
        g=float(np.clip(raw_g*aw[i]*scale,-max_db,max_db))
        if warmth_ok and 400<=fc<=1600 and g<-0.3 and abs(raw_g)<4.0:
            g=max(g*0.08,-0.20)
        if crest_headroom<-1.5 and fc<=400 and g>0:
            g=g*0.20
        if abs(g)>=0.28 and abs(g-prev_g)<5.0:
            Q=1.2 if abs(g)<2 else 0.85
            nodes.append((float(fc),round(g,2),Q))
        prev_g=g
    return nodes

# ══════════════════════════════════════════════════════════════════════════════
#  QUALITY SCORE — v8.5 TIER-ADJUSTED SCORING
#  score_tier:     vs achievable targets for source tier (displayed to user)
#  score_absolute: vs original 1425H targets always (honest reference)
# ══════════════════════════════════════════════════════════════════════════════

def quality_score(out_b:Dict,ref_fp:ReferenceFingerprint,
                  metrics:Dict,hf_rolloff:float=20000.0,
                  source_tier:str='TIER_PRISTINE',
                  input_cutoff_hz:float=20000.0) -> Tuple[float,QualityReport]:
    ref_b=ref_fp.third_oct
    ceil=min(10000,int(hf_rolloff*0.85))
    common=[fc for fc in out_b if fc in ref_b and 80<=fc<=ceil]

    if common:
        out_v=np.array([out_b[fc] for fc in common])
        ref_v=np.array([ref_b[fc] for fc in common])
        aw=np.array([max(0.2,1+A_WEIGHT.get(fc,0)/10) for fc in common])
        loff=float(np.mean(ref_v-out_v))
        diffs=np.abs((ref_v-out_v)-loff)
        w_avg=float(np.sum(aw*diffs)/np.sum(aw))
        spectral_s=max(0.0,100.0-w_avg*4.5)
    else:
        w_avg=99.0; spectral_s=0.0

    lra_t = ref_fp.lra  # 4.19 (صحيح منذ v7.6)

    tfc = np.array([fc for fc in CENTERS_31 if 200 <= fc <= 2000
                    and fc in out_b and fc < hf_rolloff], dtype=float)
    out_tilt = (float(np.polyfit(np.log2(tfc / 1000.0),
                                 np.array([out_b[fc] for fc in tfc]), 1)[0])
                if len(tfc) >= 3 else 0.0)
    warmth_s = max(0.0, 100.0 - abs(out_tilt - ref_fp.warmth_ratio) * 5.5)

    hf_fcs = [fc for fc in [4000, 5000, 6300, 8000, 10000, 12500]
              if fc < hf_rolloff and fc in out_b and fc in ref_b]
    if len(hf_fcs) >= 3:
        hf_o = np.array([out_b[fc] for fc in hf_fcs])
        hf_r = np.array([ref_b[fc] for fc in hf_fcs])
        hf_e = float(np.mean(np.abs((hf_r - hf_o) - float(np.mean(hf_r - hf_o)))))
        hf_s = max(0.0, 100.0 - hf_e * 4)
    else:
        hf_s = 50.0

    lufs_val  = metrics.get('lufs',  -20)
    crest_val = metrics.get('crest',  15)
    lra_val   = metrics.get('lra',     8)

    # ── score_absolute: vs original 1425H targets — never changes ─────────────────
    lufs_s_a  = max(0.0, 100.0 - abs(lufs_val  - TARGET['lufs'])  * 12)
    crest_s_a = max(0.0, 100.0 - abs(crest_val - TARGET['crest']) *  8)
    lra_s_a   = max(0.0, 100.0 - abs(lra_val   - lra_t)           * 10)
    score_absolute = round(
        spectral_s * 0.38 + lufs_s_a * 0.20 + crest_s_a * 0.15 +
        lra_s_a    * 0.12 + warmth_s * 0.10 + hf_s      * 0.05, 1)

    # ── score_tier: vs achievable targets for this source tier ────────────────
    # v8.5 TierAdjustedScoring: replaces ad-hoc 64K_FLOOR hack.
    # A 64kbps file that reaches its physical ceiling is not a processing failure.
    at = _compute_achievable_targets(source_tier, input_cutoff_hz)
    lufs_s_t  = max(0.0, 100.0 - abs(lufs_val  - at['lufs'])  * 12)
    crest_s_t = max(0.0, 100.0 - abs(crest_val - at['crest']) *  8)
    lra_s_t   = max(0.0, 100.0 - abs(lra_val   - at['lra'])   * 10)
    score_tier = round(
        spectral_s * 0.38 + lufs_s_t * 0.20 + crest_s_t * 0.15 +
        lra_s_t    * 0.12 + warmth_s * 0.10 + hf_s      * 0.05, 1)

    # ── ceiling_reason — logged when tier relaxes targets ──────────────────────
    ceiling_reason = ''
    if source_tier != 'TIER_PRISTINE':
        ceiling_reason = (
            f"{source_tier}: Crest≤{at['crest']:.2f}LU  "
            f"LRA≤{at['lra']:.2f}LU  LUFS≥{at['lufs']:.2f}  "
            f"[cutoff={input_cutoff_hz:.0f}Hz]"
        )

    notes = []
    if abs(lufs_val - TARGET['lufs']) > 0.6:
        notes.append(f"LUFS:{lufs_val:.2f}→{TARGET['lufs']}")
    if abs(crest_val - at['crest']) > 1.2:
        notes.append(f"Crest:{crest_val:.2f}→{at['crest']:.2f}")
    if abs(lra_val - at['lra']) > 1.0:
        notes.append(f"LRA:{lra_val:.2f}→{at['lra']:.2f}")
    if w_avg > 2.5:
        notes.append(f"Spectral:±{w_avg:.2f}dB")

    rpt = QualityReport(
        score          = score_tier,
        spectral       = round(spectral_s, 1),
        lufs           = round(lufs_s_a, 1),
        crest          = round(crest_s_a, 1),
        lra            = round(lra_s_a, 1),
        warmth         = round(warmth_s, 1),
        hf             = round(hf_s, 1),
        avg_err        = round(w_avg, 2),
        warmth_tilt    = round(out_tilt, 2),
        warmth_ref     = round(ref_fp.warmth_ratio, 2),
        lra_target     = round(lra_t, 2),
        notes          = notes,
        score_absolute = score_absolute,
        score_tier     = score_tier,
        ceiling_reason = ceiling_reason,
    )
    return rpt.score, rpt

# ══════════════════════════════════════════════════════════════════════════════
#  9-SEGMENT FULL-FILE SPECTRAL AVERAGE
# ══════════════════════════════════════════════════════════════════════════════

def analyze_full_spectrum(input_path:str,total_s:int) -> Dict[float,float]:
    pcts=[0.10,0.20,0.30,0.40,0.50,0.60,0.70,0.80,0.90]
    skips=[max(10,int(total_s*p)) for p in pcts]
    clips=[os.path.join(_TMP, f'v81_seg{i}.wav') for i in range(len(skips))]
    procs=[subprocess.Popen(['ffmpeg','-y','-i',input_path,
            '-ss',str(sk),'-t','20','-f','s16le','-ac','1',
            '-ar',str(SR),cl,'-loglevel','error'])
           for sk,cl in zip(skips,clips)]
    for p in procs: p.wait()
    all_bands:List[Dict]=[]
    for cl in clips:
        try:
            if not os.path.exists(cl) or os.path.getsize(cl)<SR*2: continue
            a=np.frombuffer(open(cl,'rb').read(),np.int16).astype(np.float32)/32768.0
            if len(a)<SR*3: continue
            all_bands.append(third_octave(a,a_weighted=False))
        except: pass
    if not all_bands: return {}
    result={}
    for fc in CENTERS_31:
        vals=[b.get(fc) for b in all_bands if b.get(fc) is not None]
        if len(vals)>=2: result[fc]=float(np.median(vals))
    return result

# ══════════════════════════════════════════════════════════════════════════════
#  REFERENCE FINGERPRINT
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  v8.45 — DEEP REFERENCE MODEL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _phrase_lra_dist(audio: 'np.ndarray', sr: int = SR,
                     min_phrase_s: float = 1.0) -> 'Tuple[float,float,float,int]':
    """
    Phrase-level LRA distribution for dense Quran recitation.
    Uses energy-dip detection (works for continuous recitation with short breath pauses).
    Returns (p10, p50, p90, n_phrases).  Bypass: returns (0,0,0,0) if audio too short.
    """
    if len(audio) < sr * 10:
        return 0.0, 0.0, 0.0, 0
    frame = int(0.01 * sr)
    hop   = int(0.005 * sr)
    # Short-time RMS energy in dBFS
    energies = np.array([
        rms_db(audio[i:i+frame])
        for i in range(0, len(audio) - frame, hop)
    ], dtype=np.float32)
    # 50ms smoothing
    k = max(1, int(0.05 / 0.005))
    smooth = np.convolve(energies, np.ones(k)/k, mode='same')
    # Running max in 2s window
    win2 = int(2.0 / 0.005)
    run_max = np.array([
        np.max(smooth[max(0, i-win2):i+win2])
        for i in range(len(smooth))
    ])
    # Dip = energy 3dB below local max
    is_dip = smooth < (run_max - 3.0)
    # Collect phrase boundaries
    gap_frames = int(0.25 / 0.005)
    min_frames = int(min_phrase_s / 0.005)
    phrases: List['np.ndarray'] = []
    in_ph = False; start = 0; gap = 0
    for i, dip in enumerate(is_dip):
        if not dip:
            if not in_ph:
                start = i
            in_ph = True
            gap = 0
        else:
            if in_ph:
                gap += 1
                if gap > gap_frames:
                    dur = i - gap - start
                    if dur > min_frames:
                        s_samp = start * hop
                        e_samp = (i - gap) * hop
                        if e_samp > s_samp + sr:
                            phrases.append(audio[s_samp:e_samp])
                    in_ph = False
                    gap = 0
    if in_ph:
        phrases.append(audio[start*hop:])
    lras = [lra_estimate(ph) for ph in phrases if len(ph) > sr * 0.5]
    if len(lras) < 3:
        return 0.0, 0.0, 0.0, 0
    return (round(float(np.percentile(lras, 10)), 2),
            round(float(np.percentile(lras, 50)), 2),
            round(float(np.percentile(lras, 90)), 2),
            len(lras))


def _ref_silence_floor(audio: 'np.ndarray', sr: int = SR) -> float:
    """
    Noise floor of the reference recording measured from silent frames.
    Sets the NR ceiling: never push noise below (silence_floor_db - 3dB).
    Returns dBFS float.  Bypass: -70.0 if no silence frames found.
    """
    frame = int(0.025 * sr)
    hop   = int(0.010 * sr)
    overall_rms = rms_db(audio)
    threshold   = overall_rms - 20.0   # 20dB below voiced level
    floors = [
        rms_db(audio[i:i+frame])
        for i in range(0, len(audio) - frame, hop)
        if rms_db(audio[i:i+frame]) < threshold
    ]
    if len(floors) < 20:
        return -70.0
    # Use p50 of silence frames (robust against burst noise)
    return float(np.percentile(floors, 50))


def _ref_codec_cutoff(audio: 'np.ndarray', sr: int = SR) -> float:
    """
    Detects the highest frequency with genuine content in the reference file.
    Used to prevent BIAS boosts targeting frequencies the ref itself doesn't contain.
    Returns Hz float.
    """
    n_fft = min(131072, len(audio))
    if n_fft < sr:
        return 14000.0
    wins = []
    for i in range(0, len(audio) - n_fft, n_fft * 2):
        seg = audio[i:i+n_fft].astype(np.float64)
        wins.append(np.abs(rfft(seg * np.hanning(n_fft)))**2)
    if not wins:
        return 14000.0
    X = np.mean(wins, axis=0)
    freqs = rfftfreq(n_fft, 1.0/sr)
    # Reference level: RMS energy at 1-2kHz
    mask_1k = (freqs >= 1000) & (freqs < 2000)
    if not mask_1k.any():
        return 14000.0
    ref_db = 10 * np.log10(np.mean(X[mask_1k]) + 1e-30)
    # Scan down from 20kHz; first band where energy is within 45dB of 1kHz ref = cutoff
    for fc in [20000, 18000, 17000, 16000, 15000, 14000, 13000, 12000, 11000, 10000, 8000]:
        lo, hi = fc - 500, min(fc + 500, sr // 2 - 1)
        mask = (freqs >= lo) & (freqs < hi)
        if not mask.any():
            continue
        band_db = 10 * np.log10(np.mean(X[mask]) + 1e-30)
        if band_db > ref_db - 45.0:
            return float(fc)
    return 8000.0


def _full_file_third_oct_avg(audio: 'np.ndarray', sr: int = SR,
                              window_s: float = 10.0, hop_s: float = 60.0) -> Dict[float, float]:
    """
    Full-file spectral average using windowed sampling (every hop_s seconds).
    Replaces the 8 fixed-position 30s clip approach.

    FORENSIC JUSTIFICATION: actual measurements showed 40s-clip spectral values
    differed from full-file averages by up to +16dB at 2kHz on Al-Araaf, and
    +12dB at 8kHz on Al-Fatir. The clip was capturing atypical opening material,
    not the Sheikh's settled recitation.
    """
    win   = int(window_s * sr)
    hop   = int(hop_s   * sr)
    overall_rms = rms_db(audio)
    silence_thr = overall_rms - 25.0   # skip near-silence windows
    spectra: List[Dict[float, float]] = []
    for start in range(0, len(audio) - win, hop):
        seg = audio[start:start+win]
        if rms_db(seg) > silence_thr:
            spectra.append(third_octave(seg.astype(np.float32)))
    if not spectra:
        return third_octave(audio[:win].astype(np.float32))
    avg: Dict[float, float] = {}
    for fc in spectra[0]:
        vals = [s[fc] for s in spectra if fc in s]
        if vals:
            avg[fc] = float(np.mean(vals))
    return avg


def _peak_distribution_type(audio: 'np.ndarray', sr: int = SR) -> str:
    """
    Classifies whether energy peaks occur at phrase attacks (front_loaded),
    uniformly throughout phrases, or at the end (back_loaded).
    Used to shape compand attack time in Pass 3.
    """
    frame = int(0.02 * sr)
    hop   = int(0.01 * sr)
    energies = np.array([
        rms_db(audio[i:i+frame])
        for i in range(0, len(audio) - frame, hop)
    ], dtype=np.float32)
    threshold = float(np.percentile(energies[energies > -60], 30)) - 3 if np.any(energies > -60) else -40.0
    is_voiced = energies > threshold
    gap_frames  = int(0.3 / 0.01)
    min_frames  = int(0.8 / 0.01)
    ratios: List[float] = []
    in_ph = False; start = 0; gap = 0
    for i, v in enumerate(is_voiced):
        if v:
            if not in_ph:
                start = i
            in_ph = True
            gap = 0
        else:
            if in_ph:
                gap += 1
                if gap > gap_frames:
                    dur = i - gap - start
                    if dur > min_frames:
                        ph = energies[start:i - gap]
                        attack = ph[:max(1, int(len(ph) * 0.12))]
                        if len(attack) and len(ph) > len(attack):
                            ratios.append(float(np.max(attack)) - float(np.max(ph[len(attack):])))
                    in_ph = False
                    gap = 0
    if len(ratios) < 3:
        return 'uniform'
    mean_r = float(np.mean(ratios))
    if mean_r > 1.0:
        return 'front_loaded'
    elif mean_r > -1.5:
        return 'uniform'
    else:
        return 'back_loaded'


# ══════════════════════════════════════════════════════════════════════════════
#  v8.7 — NR/EQ COORDINATOR + SIBILANT SMEAR + BSR
# ══════════════════════════════════════════════════════════════════════════════

def measure_post_nr_spectrum(input_path: str, nr_parts: 'List[str]',
                              skip_s: int, dur_s: int,
                              sr: int = SR) -> 'Dict[float, float]':
    """
    v8.7: Run NR chain on a 30s sample, return resulting third_octave.
    Used as EQ basis instead of inp_b (pre-NR spectrum).

    WHY: optimize_eq() was computing corrections against the pre-NR spectrum.
    NR changes the spectrum (up to 10dB at 4-8kHz on DEGRADED sources).
    EQ corrections computed from the wrong baseline go in the wrong direction.

    Returns empty dict if nr_parts is empty (caller falls back to inp_b).
    """
    if not nr_parts:
        return {}
    tmp_nr = os.path.join(_TMP, 'v87_nr_meas.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', input_path,
         '-ss', str(skip_s), '-t', str(min(30, max(10, dur_s))),
         '-af', ','.join(nr_parts),
         '-ar', str(sr), '-ac', '1', tmp_nr, '-loglevel', 'error'],
        capture_output=True)
    if r.returncode != 0 or not os.path.exists(tmp_nr):
        return {}
    try:
        raw = open(tmp_nr, 'rb').read()[44:]   # skip WAV header
        a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
        if len(a) < sr * 5:
            return {}
        return third_octave(a)
    except Exception:
        return {}
    finally:
        try: os.unlink(tmp_nr)
        except: pass


def detect_sibilant_smear(audio: 'np.ndarray', sr: int = SR) -> 'Tuple[float, str]':
    """
    v8.7: Diagnosis only. No correction in this version.
    Measures harmonic ratio of voiced fricative frames (\u0634/\u0633/\u0635 segments).

    In clean 128kbps+ recordings the 2-6kHz band of fricative frames shows
    clear harmonic peaks (ratio ~0.35-0.55).  At 32kbps, codec smear flattens
    those peaks to broadband noise (ratio ~0.08-0.20).

    Returns (smear_score 0-10, description).
    smear_score >= 6: v8.8 correction planned.
    """
    if not NUMPY_OK or len(audio) < sr * 5:
        return 0.0, 'insufficient_audio'
    frame_n = int(0.025 * sr)
    hop_n   = int(0.010 * sr)
    overall_rms = rms_db(audio)
    lo, hi = overall_rms - 15.0, overall_rms - 3.0
    harmonic_ratios: List[float] = []
    for i in range(0, len(audio) - frame_n, hop_n):
        f = audio[i:i+frame_n]
        if len(f) < frame_n:
            continue
        f_rms = rms_db(f)
        if not (lo < f_rms < hi):
            continue
        spec  = np.abs(rfft(f * np.hanning(frame_n))) ** 2
        freqs = rfftfreq(frame_n, 1.0 / sr)
        mask  = (freqs >= 2000) & (freqs <= 6000)
        if not mask.any():
            continue
        band  = spec[mask]
        thr   = float(np.mean(band) + np.std(band))
        peak_e  = float(np.sum(band[band > thr]))
        total_e = float(np.sum(band) + 1e-30)
        harmonic_ratios.append(peak_e / total_e)
        if len(harmonic_ratios) >= 80:
            break
    if len(harmonic_ratios) < 10:
        return 0.0, 'no_fricative_frames'
    median_r    = float(np.median(harmonic_ratios))
    smear_score = float(np.clip((0.45 - median_r) / 0.40 * 10, 0, 10))
    if smear_score < 2:   desc = 'clean'
    elif smear_score < 4: desc = 'mild_smear'
    elif smear_score < 7: desc = 'moderate_smear'
    else:                  desc = 'severe_smear'
    return round(smear_score, 1), desc


class BroadbandStaticReducer:
    """
    v8.7: Wiener-inspired spectral subtraction via afftdn.
    NR ceiling = ref_fp.silence_floor_db - 3dB. Never lower.
    Do-No-Harm gate: revert if sibilant SNR drops > 3dB.
    """

    @staticmethod
    def should_apply(silence: 'SilenceProfile', noise_type: str,
                     clip_tier: str, tier: str) -> bool:
        if not silence.valid:               return False
        if noise_type == 'none':            return False
        if clip_tier == 'severe':           return False
        if tier == 'TIER_PRISTINE':         return False
        return silence.noise_sfm > 0.35 and silence.n_silence_frames >= 5

    @staticmethod
    def build_chain(silence: 'SilenceProfile',
                    ref_nr_floor: float, tier: str) -> str:
        measured_nf = float(silence.floor_dbfs + 2.0)
        nf = float(np.clip(max(measured_nf, ref_nr_floor), -76, -40))
        max_nr = {'TIER_DAMAGED': 15, 'TIER_DEGRADED': 10,
                  'TIER_COMPRESSED': 6}.get(tier, 5)
        nr_depth = max(3, min(max_nr, int(abs(silence.floor_dbfs) * 0.18)))
        return f'afftdn=nr={nr_depth}:nf={nf:.0f}:tn=1'

    @staticmethod
    def apply_and_verify(input_path: str, chain: str,
                         skip_s: int, sr: int, L) -> 'Tuple[str, bool]':
        pre_a = load_audio(input_path, sr=sr, skip=skip_s, duration=30)
        if len(pre_a) < sr * 5:
            return input_path, False
        pre_bsnr = compute_band_snr(pre_a)
        pre_sib  = float(np.mean([pre_bsnr.get(4000.0, 10.0),
                                   pre_bsnr.get(8000.0, 10.0)]))
        tmp_bsr = os.path.join(_TMP, 'v87_bsr.wav')
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', input_path, '-af', chain,
             '-ar', str(sr), '-ac', '2', tmp_bsr, '-loglevel', 'error'],
            capture_output=True)
        if r.returncode != 0 or not os.path.exists(tmp_bsr):
            return input_path, False
        post_a   = load_audio(tmp_bsr, sr=sr, skip=skip_s, duration=30)
        post_bsnr = compute_band_snr(post_a)
        post_sib  = float(np.mean([post_bsnr.get(4000.0, 10.0),
                                    post_bsnr.get(8000.0, 10.0)]))
        sib_drop = pre_sib - post_sib
        L(f"  [BSR] sibilant_snr: {pre_sib:.1f} → {post_sib:.1f}dB"
          f"  (Δ={-sib_drop:+.1f})")
        if sib_drop > 3.0:
            L(f"  [BSR] ⚠ drop {sib_drop:.1f}dB > 3dB — Do-No-Harm revert")
            try: os.unlink(tmp_bsr)
            except: pass
            return input_path, False
        return tmp_bsr, True


def get_reference_fingerprint() -> ReferenceFingerprint:
    # v8.1 PATCH #2: REF_FILES may be empty — guard primary access
    primary = REF_FILES[0] if REF_FILES else ''

    # v8.1 PATCH #1: REF_CACHE is now in Path.home()/.tilawa_cache/
    if os.path.exists(REF_CACHE):
        try:
            mref=os.path.getmtime(primary) if os.path.exists(primary) else 0
            if os.path.getmtime(REF_CACHE)>=mref:
                with open(REF_CACHE,'r',encoding='utf-8') as f: d=json.load(f)
                if d.get('version') in ('v8.1', 'v8.45'):
                    fp = ReferenceFingerprint()
                    fp.third_oct    = {float(k):v for k,v in d['third_oct'].items()}
                    fp.a_weighted   = {float(k):v for k,v in d.get('a_weighted',{}).items()}
                    fp.rms          = d['rms'];  fp.peak = d['peak']
                    fp.crest        = d['crest']
                    fp.lra          = d.get('lra',         TARGET['lra'])
                    fp.lra_clip     = d.get('lra_clip',    2.94)
                    fp.tilt_slope   = d['tilt_slope']
                    fp.warmth_ratio = d['warmth_ratio']
                    fp.sfm          = d.get('sfm',         TARGET['sfm'])
                    fp.dr           = d.get('dr',          TARGET['dr'])
                    fp.n_files      = d.get('n_files',     1)
                    # v8.45 deep fields (graceful fallback if cache is v8.1)
                    fp.phrase_lra_p10      = d.get('phrase_lra_p10',      2.50)
                    fp.phrase_lra_p50      = d.get('phrase_lra_p50',      3.37)
                    fp.phrase_lra_p90      = d.get('phrase_lra_p90',      4.20)
                    fp.silence_floor_db    = d.get('silence_floor_db',    -73.0)
                    fp.ref_codec_cutoff_hz = d.get('ref_codec_cutoff_hz', 14000.0)
                    fp.peak_distribution   = d.get('peak_distribution',   'uniform')
                    return fp
        except: pass

    # ── v8.45: full-file windowed analysis replaces 8×30s fixed clips ──────────
    # FORENSIC: 40s clip differed from full-file by up to +16dB at 2kHz (Al-Araaf),
    # +12dB at 8kHz (Al-Fatir). The clips were capturing atypical opening material.
    all_fp:List[Dict]=[]

    for idx, path in enumerate(REF_FILES):
        if not os.path.exists(path):
            continue
        try:
            # Load the full reference file as float32 mono at SR
            tmp_full = os.path.join(_TMP, f'v845_ref_full_{idx}.wav')
            subprocess.run(
                ['ffmpeg', '-y', '-i', path,
                 '-ac', '1', '-ar', str(SR), tmp_full, '-loglevel', 'error'],
                capture_output=True)
            if not os.path.exists(tmp_full) or os.path.getsize(tmp_full) < SR * 4:
                continue
            full_a = np.frombuffer(open(tmp_full,'rb').read()[44:],
                                   np.int16).astype(np.float32) / 32768.0
            if len(full_a) < SR * 10:
                continue

            # Full-file spectral average (v8.45 core improvement)
            spec_full = _full_file_third_oct_avg(full_a, SR)

            # Basic metrics from the full file
            all_fp.append({
                'spec':      spec_full,
                'rms':       float(rms_db(full_a)),
                'crest':     float(crest_factor(full_a)),
                'lra_full':  float(lra_estimate(full_a)),
                'lra_clip':  float(lra_estimate(full_a[:SR*30])),  # first 30s for compand compat
                'sfm':       float(compute_sfm(full_a)),
                'dr':        float(compute_dynamic_range(full_a)),
                # v8.45 deep fields
                'phrase_lra':     _phrase_lra_dist(full_a, SR),
                'silence_floor':  _ref_silence_floor(full_a, SR),
                'codec_cutoff':   _ref_codec_cutoff(full_a, SR),
                'peak_dist':      _peak_distribution_type(full_a, SR),
            })
            try: os.unlink(tmp_full)
            except: pass
        except Exception:
            continue

    if len(all_fp) < 2:
        fp = _build_single_ref(primary) if os.path.exists(primary) else ReferenceFingerprint()
        fp.n_files = len(all_fp) or 1
        return fp

    # ── Multi-ref averaging ───────────────────────────────────────────────────
    ref_lvl     = float(np.mean([f['rms'] for f in all_fp]))
    common_all  = [fc for fc in CENTERS_31 if all(fc in f['spec'] for f in all_fp)]
    normed      = [{fc: f['spec'][fc] + (ref_lvl - f['rms']) for fc in common_all}
                   for f in all_fp]
    multi       = {fc: float(np.median([s[fc] for s in normed])) for fc in common_all}

    fp = ReferenceFingerprint()
    fp.third_oct    = multi
    fp.rms          = float(np.median([f['rms']       for f in all_fp]))
    fp.peak         = TARGET['true_peak']
    fp.crest        = float(np.median([f['crest']     for f in all_fp]))
    fp.lra_clip     = float(np.median([f['lra_clip']  for f in all_fp]))
    fp.lra          = float(np.median([f['lra_full']  for f in all_fp]))  # v8.45: real full-file LRA
    fp.sfm          = float(np.median([f['sfm']       for f in all_fp]))
    fp.dr           = float(np.median([f['dr']        for f in all_fp]))
    fp.n_files      = len(all_fp)
    fp.tilt_slope   = spectral_tilt(fp.third_oct)
    fp.warmth_ratio = warmth_tilt(fp.third_oct)

    # ── v8.45 deep reference fields ───────────────────────────────────────────
    # phrase LRA: p50 is the Pass 3 compand target
    all_p50 = [f['phrase_lra'][1] for f in all_fp if f['phrase_lra'][2] > 0]
    all_p10 = [f['phrase_lra'][0] for f in all_fp if f['phrase_lra'][2] > 0]
    all_p90 = [f['phrase_lra'][2] for f in all_fp if f['phrase_lra'][2] > 0]
    if all_p50:
        fp.phrase_lra_p50 = float(np.median(all_p50))
        fp.phrase_lra_p10 = float(np.median(all_p10))
        fp.phrase_lra_p90 = float(np.median(all_p90))
    # silence floor: use the highest (least quiet) floor across refs as the
    # safe NR ceiling — conservative choice prevents over-denoising
    floors = [f['silence_floor'] for f in all_fp if f['silence_floor'] < -20]
    fp.silence_floor_db = float(max(floors)) if floors else -70.0
    # codec cutoff: use minimum across refs — don't target HF that some refs lack
    cutoffs = [f['codec_cutoff'] for f in all_fp]
    fp.ref_codec_cutoff_hz = float(min(cutoffs))
    # peak distribution: majority vote
    from collections import Counter
    peak_votes = Counter(f['peak_dist'] for f in all_fp)
    fp.peak_distribution = peak_votes.most_common(1)[0][0]

    # Warn if any ref has suspect cutoff (may have been re-encoded from low bitrate)
    for i, f in enumerate(all_fp):
        if f['codec_cutoff'] < 12000:
            print(f"  [v8.45] ⚠ REF_WARN: ref[{i}] codec_cutoff={f['codec_cutoff']:.0f}Hz "
                  f"-- may be re-encoded from low bitrate")

    try:
        p_info = probe(primary)
        ts = int(float(p_info.get('format', {}).get('duration', 300)))
        pa = load_audio(primary, skip=int(ts * 0.35), duration=60)
        fp.a_weighted = third_octave(pa, a_weighted=True)
    except:
        pass

    # ── Cache write: v8.45 format ─────────────────────────────────────────────
    try:
        Path(REF_CACHE).parent.mkdir(parents=True, exist_ok=True)
        d = {
            'version':          'v8.45',
            'third_oct':        {str(k): v for k, v in fp.third_oct.items()},
            'a_weighted':       {str(k): v for k, v in fp.a_weighted.items()},
            'rms':              fp.rms,
            'peak':             fp.peak,
            'crest':            fp.crest,
            'lra':              fp.lra,
            'lra_clip':         fp.lra_clip,
            'tilt_slope':       fp.tilt_slope,
            'warmth_ratio':     fp.warmth_ratio,
            'sfm':              fp.sfm,
            'dr':               fp.dr,
            'n_files':          fp.n_files,
            # v8.45 deep fields
            'phrase_lra_p10':      fp.phrase_lra_p10,
            'phrase_lra_p50':      fp.phrase_lra_p50,
            'phrase_lra_p90':      fp.phrase_lra_p90,
            'silence_floor_db':    fp.silence_floor_db,
            'ref_codec_cutoff_hz': fp.ref_codec_cutoff_hz,
            'peak_distribution':   fp.peak_distribution,
        }
        with open(REF_CACHE, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return fp

def _build_single_ref(path:str) -> ReferenceFingerprint:
    p_info=probe(path); total_s=int(float(p_info.get('format',{}).get('duration',300)))
    skips=[max(10,int(total_s*r)) for r in [0.12,0.28,0.44,0.60,0.78]]
    clips=[os.path.join(_TMP, f'v81_ref_s{i}.wav') for i in range(len(skips))]
    procs=[subprocess.Popen(['ffmpeg','-y','-i',path,'-ss',str(sk),'-t','40',
            '-f','s16le','-ac','1','-ar',str(SR),cl,'-loglevel','error'])
           for sk,cl in zip(skips,clips)]
    for p in procs: p.wait()
    segs=[]
    for cl in clips:
        try:
            a=np.frombuffer(open(cl,'rb').read(),np.int16).astype(np.float32)/32768.0
            if len(a)>SR: segs.append(a)
        except: pass
    ref=np.concatenate(segs) if segs else load_audio(path,skip=30,duration=120)
    chunk_n=SR*20; all_b=[]; crests=[]; lras=[]; sfms=[]; drs=[]
    for ci in range(max(1,len(ref)//chunk_n)):
        seg=ref[ci*chunk_n:(ci+1)*chunk_n]
        if len(seg)<SR*3: continue
        all_b.append(third_octave(seg)); crests.append(crest_factor(seg))
        lras.append(lra_estimate(seg)); sfms.append(compute_sfm(seg))
        drs.append(compute_dynamic_range(seg))
    if not all_b: all_b=[third_octave(ref)]
    fp=ReferenceFingerprint()
    for fc in CENTERS_31:
        vals=[b.get(fc) for b in all_b if b.get(fc) is not None]
        if vals: fp.third_oct[fc]=float(np.median(vals))
    fp.rms=rms_db(ref); fp.peak=peak_db(ref)
    fp.crest   =float(np.median(crests)) if crests else crest_factor(ref)
    fp.lra_clip=float(np.median(lras))   if lras   else lra_estimate(ref)
    fp.lra     =TARGET['lra']
    fp.sfm     =float(np.median(sfms))   if sfms   else TARGET['sfm']
    fp.dr      =float(np.median(drs))    if drs    else TARGET['dr']
    fp.tilt_slope=spectral_tilt(fp.third_oct)
    fp.warmth_ratio=warmth_tilt(fp.third_oct)
    fp.n_files=1; return fp

# ══════════════════════════════════════════════════════════════════════════════
#  LUFS SAMPLING
# ══════════════════════════════════════════════════════════════════════════════

def sample_lufs_7pt(input_path:str,total_s:int,n_ch:str,filter_str:str) -> float:
    pts=[max(10,int(total_s*p)) for p in [0.08,0.18,0.32,0.50,0.65,0.78,0.90]]
    for i in range(1,len(pts)):
        if pts[i]-pts[i-1]<30: pts[i]=pts[i-1]+30
    clips=[os.path.join(_TMP, f'v81_lc{i}.wav') for i in range(len(pts))]
    procs=[subprocess.Popen(['ffmpeg','-y','-i',input_path,
            '-ss',str(sk),'-t','22','-ar','48000','-ac',n_ch,
            cl,'-loglevel','error']) for sk,cl in zip(pts,clips)]
    for p in procs: p.wait()
    lp=[subprocess.Popen(['ffmpeg','-y','-i',cl,'-af',
         filter_str+',ebur128=peak=true','-f','null','-','-loglevel','info'],
         stderr=subprocess.PIPE,stdout=subprocess.PIPE) for cl in clips]
    vals:List[float]=[]
    for p in lp:
        _,err=p.communicate()
        for line in err.decode().split('\n'):
            s=line.strip()
            if s.startswith('I:') and 'LUFS' in s and 'LRA' not in s:
                try: vals.append(float(s.split('I:')[1].strip().split()[0])); break
                except: pass
    if not vals: return -12.0
    gw=[0.05,0.12,0.20,0.26,0.20,0.12,0.05][:len(vals)]
    gw=[w/sum(gw) for w in gw]
    return float(np.average(vals,weights=gw))

# ══════════════════════════════════════════════════════════════════════════════
#  FILTER CHAIN BUILDER — v8 BUG #2 + #3 FIX
# ══════════════════════════════════════════════════════════════════════════════

def build_filter_chain(eq_nodes:List[Tuple],compand_pts:str,makeup:float,
                       hf:str,is_mono:bool,gain_db:float,
                       nr_parts:List[str],bias_filter:str,
                       warmth_pre:List[Tuple],intensity:str,
                       inp_lra:float,damage:DamageProfile,
                       hf_rolloff:float,src_sr:int,
                       ref_lra_clip:float,tilt_slope:float,
                       correction_nodes:List[Tuple]=None,
                       post_warmth:List[Tuple]=None) -> str:
    """
    v8 FIX #2: حذف LRA compand من الـ chain — compand رئيسي واحد فقط
    v8 FIX #3: alimiter واحد ناعم (0.9997) في WAV الوسيطة بدل 0.891
    """
    if correction_nodes is None: correction_nodes=[]
    if post_warmth is None:      post_warmth=[]
    parts:List[str]=[]; is_bypass=(intensity=='BYPASS')
    is_extreme=(damage.quality_label=='EXTREME')

    # 1. DC blocking
    parts.append('highpass=f=28:poles=2')

    # 2. NR
    parts.extend(nr_parts)

    # 3. Tilt correction
    if not is_bypass and abs(tilt_slope)>1.0:
        db=min(abs(tilt_slope)*0.35,5.0)
        if tilt_slope>0: parts.append(f'treble=g={db:.1f}:f=8000:width_type=o:width=2')
        else:            parts.append(f'bass=g={db:.1f}:f=150:width_type=o:width=2')

    # 4. Perceptual EQ (scipy Bark + A-weight)
    for f0,g,Q in eq_nodes:
        parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}')

    # 5. Warmth pre-compand (Crest-aware)
    for f0,g,Q in warmth_pre:
        parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}')

    # 6. HF reconstruction (v8.7: crystalizer removed -- aexciter+treble only)
    # PHYSICS: crystalizer synthesises harmonics from aperiodic noise above cutoff.
    # Arabic fricatives (\u0634/\u0633/\u0635) are aperiodic -- crystalizer produces
    # ringing artifacts on sibilants. aexciter is bounded to content that already
    # exists below hf_rolloff; drive=2.0 adds ~1.5dB presence (audibly gentle).
    if not is_bypass:
        if is_extreme:
            exc_freq = max(3000, int(hf_rolloff * 0.72))
            parts.append(f'aexciter=freq={exc_freq}:type=2:listen=0'
                         f':level_in=1:level_out=1:drive=2.0:blend=0')
            parts.append('treble=g=2.5:f=5000:width_type=o:width=1.5')
            if hf_rolloff < 8000:
                parts.append(f'treble=g=1.5:f={max(2000,int(hf_rolloff*0.65))}'
                             f':width_type=o:width=2')
        elif damage.quality_label == 'VERY_POOR':
            exc_freq = max(3500, int(hf_rolloff * 0.78))
            parts.append(f'aexciter=freq={exc_freq}:type=2:listen=0'
                         f':level_in=1:level_out=1:drive=1.5:blend=0')
            parts.append('treble=g=1.5:f=6000:width_type=o:width=2')
        elif damage.quality_label in ('POOR', 'GOOD', 'FAIR'):
            # No aexciter for POOR/FAIR -- treble shelf only on absent HF
            if hf == 'absent':
                shelf_hz = max(4000, int(hf_rolloff * 0.82))
                parts.append(f'treble=g=2.0:f={shelf_hz}:width_type=o:width=2')
            elif hf == 'weak':
                shelf_hz = max(4000, int(hf_rolloff * 0.85))
                parts.append(f'treble=g=1.2:f={shelf_hz}:width_type=o:width=2')

    # 7. Post-NR
    if not is_bypass and nr_parts:
        if is_extreme: parts.append('afftdn=nr=4:nf=-80:tn=0')
        elif damage.quality_label in ('POOR','VERY_POOR'):
            parts.append('afftdn=nr=6:nf=-74:tn=0')
        elif damage.snr<40:
            nr=max(3,min(10,int((40.0-damage.snr)*0.4)))
            parts.append(f'afftdn=nr={nr}:nf=-74:tn=1')

    # ══════════════════════════════════════════════════════════════════
    # v8 FIX #2: LRA CONTROL — agate للـ LRA المنخفض فقط
    #
    # v7.6 كان يضيف compand ثانٍ عندما inp_lra > ref_lra_clip
    # هذا كان يسبب double compression → Crest collapse
    #
    # v8: نحذف LRA compand تماماً
    #   - Low LRA (lra_deficit > 0.5): agate لتوسيع الديناميك فقط
    #   - High LRA (lra_deficit < -0.4): نتركها للـ compand الرئيسي
    #     الرعاية المتبقية تتم في Pass 3 feedback
    # ══════════════════════════════════════════════════════════════════
    lra_deficit=ref_lra_clip-inp_lra
    if not is_bypass and lra_deficit>0.5:
        # LRA منخفض جداً → agate لتوسيع النطاق الديناميكي
        ratio=min(4.0 if is_extreme else 3.5,
                  1.0+lra_deficit*(0.40 if is_extreme else 0.28))
        thr=max(0.010,min(0.045,0.022+lra_deficit*0.004))
        rel=1200 if is_extreme else 800
        parts.append(f'agate=threshold={thr:.3f}:ratio={ratio:.2f}'
                     f':attack=20:release={rel}:makeup=1.0:range=0.06')
    # v8 FIX: لا يوجد elif lra_deficit<-0.4 هنا!
    # LRA مرتفع → Main compand يعالجه | Pass 3 يعالج الباقي

    # v8.7: peak_distribution → attack time adjustment
    # front_loaded: Sheikh starts phrases strong -- slower attack preserves the transient
    # back_loaded: energy builds toward phrase end -- faster attack is fine
    _peak_dist = getattr(ref_fp, 'peak_distribution', 'uniform')
    if _peak_dist == 'front_loaded':
        atk = {k: round(v * 1.40, 4) for k, v in atk.items()}
    elif _peak_dist == 'back_loaded':
        atk = {k: round(v * 0.85, 4) for k, v in atk.items()}
    # 'uniform': no adjustment

    # 8. Compand{'MINIMAL':0.050,'LIGHT':0.030,'MEDIUM':0.015,'HEAVY':0.008,'EXTREME':0.020}
        dcy={'MINIMAL':3.0,  'LIGHT':2.0,  'MEDIUM':1.0,  'HEAVY':0.5,  'EXTREME':0.40}
        parts.append(f'compand=attacks={atk.get(intensity,0.015)}'
                     f':decays={dcy.get(intensity,1.0)}'
                     f':points={compand_pts}:gain={makeup}')

    # 9. Post-compand warmth (Crest-aware)
    for f0,g,Q in post_warmth:
        parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}')

    # 10. Spectral bias (v8 corrected)
    if not is_bypass and bias_filter:
        parts.append(bias_filter)

    # 11. Correction nodes
    for f0,g,Q in correction_nodes:
        parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}')

    # v8 FIX #3: حذف alimiter الوسيط (0.978/0.982) من هنا!
    # v7.6 كان يضيف: alimiter=limit=0.978:attack=5:release=40 هنا
    # هذا كان يسحق Crest قبل أن يصل للـ alimiter الرئيسي

    # 12. Volume
    if abs(gain_db)>0.05: parts.append(f'volume={gain_db:.3f}dB')

    # 13. Stereo
    if is_mono: parts.append('aformat=channel_layouts=stereo')

    # v8 FIX #3: alimiter ناعم جداً للـ WAV الوسيطة (يحمي من overflow فقط)
    # True Peak الحقيقي (0.891) يُطبَّق في Pass 4 فقط
    if is_bypass:
        parts.append('alimiter=limit=0.999:level=false:attack=5:release=15')
    else:
        parts.append('alimiter=limit=0.9997:level=false:attack=10:release=100')

    return ','.join(f'\n    {p}' for p in parts)

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENHANCE — v8.1
# ══════════════════════════════════════════════════════════════════════════════

def enhance(input_path:str,output_path:str,
            max_iterations:int=3,target_score:float=96.0) -> Dict:
    log:List[str]=[]; t0=time.time()
    def L(m:str='') -> None: print(m); log.append(m)

    _input_tmp=None
    try: input_path.encode('ascii')
    except UnicodeEncodeError:
        import uuid as _u2; ext=os.path.splitext(input_path)[1] or '.mp3'
        _input_tmp=os.path.join(_TMP, f'v81_in_{_u2.uuid4().hex[:8]}{ext}')
        shutil.copy2(input_path,_input_tmp); input_path=_input_tmp

    L(f"╔{'═'*70}╗")
    L(f"║  Audio Enhancement Engine v8.4 — \"Source Tier Intelligence\"         ║")
    L(f"║  المرجع: الشيخ ياسر الدوسري — 1425H                                 ║")
    L(f"║  v8.2: BIAS_SIGN ✓ | NO_STACKING ✓ | SINGLE_LIMITER ✓ | --ref ✓    ║")
    L(f"║  v8.4: SourceTierDetector ✓ | bias_cutoff ✓ | eq_ramp_scale ✓       ║")
    L(f"╚{'═'*70}╝")
    L(f"  الملف: {os.path.basename(input_path)}")

    # ── Reference ────────────────────────────────────────────────────────────
    L(f"\n[١] بصمة المرجع v8.1 (MDS: SFM + DR + Spectral Distance)...")
    ref_fp=get_reference_fingerprint()
    L(f"  ✓ {ref_fp.n_files} سورة | RMS={ref_fp.rms:.2f} Crest={ref_fp.crest:.2f}"
      f" LRA={ref_fp.lra:.2f}(full)/{ref_fp.lra_clip:.2f}(clip)")
    L(f"  ✓ SFM={ref_fp.sfm:.4f} DR={ref_fp.dr:.1f}dB"
      f" Warmth={ref_fp.warmth_ratio:.2f} Tilt={ref_fp.tilt_slope:.2f}")

    # ── File Analysis ─────────────────────────────────────────────────────────
    L(f"\n[٢] تحليل شامل (MDS: 4 مقاييس)...")
    pr=probe(input_path)
    stream=pr.get('streams',[{}])[0]
    is_mono=stream.get('channels',2)==1
    src_sr=int(stream.get('sample_rate',44100))
    src_br=int(stream.get('bit_rate',128000))
    total_s=int(float(pr.get('format',{}).get('duration',300)))
    n_ch='1' if is_mono else '2'
    # v8.7: file-length-aware analysis window (short files < 90s need smaller skip)
    if total_s <= 60:
        skip_s = max(3, total_s // 8)
        dur_s  = max(10, total_s - skip_s - 3)
    elif total_s <= 90:
        skip_s = max(5, total_s // 6)
        dur_s  = min(40, total_s - skip_s - 2)
    elif total_s <= 180:
        skip_s = min(20, total_s // 6)
        dur_s  = 45
    else:
        skip_s = min(30, total_s // 4)
        dur_s  = 45
    dur_s = max(10, dur_s)

    full_b=analyze_full_spectrum(input_path,total_s)
    inp=load_audio(input_path,skip=skip_s,duration=45)
    inp_b=full_b if full_b else third_octave(inp,a_weighted=False)

    inp_rms=rms_db(inp); inp_crest=crest_factor(inp)
    inp_lra=lra_estimate(inp); inp_hf=hf_status(inp_b)

    hf_freqs=[fc for fc in inp_b if fc>=8000]
    hf_avg=float(np.mean([inp_b[fc] for fc in hf_freqs])) if hf_freqs else -80.0
    ref_hf=float(np.mean([ref_fp.third_oct.get(fc,-60) for fc in hf_freqs])) if hf_freqs else -40.0
    hf_deficit=ref_hf-hf_avg
    hf_rolloff=max(detect_hf_rolloff(inp_b,12.0),2000.0)

    # Step 1a: SFM
    inp_sfm=compute_sfm(inp)
    sfm_ratio=inp_sfm/(ref_fp.sfm+1e-6)
    L(f"  Step 1a — SFM={inp_sfm:.4f} (ref={ref_fp.sfm:.4f}, ratio={sfm_ratio:.1f}x)")

    # Step 1b: DR
    inp_dr=compute_dynamic_range(inp)
    L(f"  Step 1b — DR={inp_dr:.1f}dB (ref={ref_fp.dr:.1f}dB, excess={inp_dr-ref_fp.dr:+.1f})")

    # Step 1c: Spectral distance
    spec_dist=compute_spectral_distance(inp_b,ref_fp,hf_rolloff)
    L(f"  Step 1c — Spectral distance=±{spec_dist:.2f}dB from 1425H")

    # Step 1d: Per-band SNR
    band_snr=compute_band_snr(inp)
    snr_global=float(np.mean(list(band_snr.values()))) if band_snr else 30.0

    # MDS
    mds=compute_mds(snr_global,inp_sfm,inp_dr,hf_deficit,spec_dist,src_br,
                    ref_fp.sfm,ref_fp.dr)
    quality_label=mds_to_label(mds)

    has_ringing=(src_br<65000)
    br_rolloff=15500.0 if src_br<65000 else 16500.0 if src_br<97000 else hf_rolloff

    damage=DamageProfile(
        snr=snr_global,sfm=inp_sfm,dr=inp_dr,hf_deficit=hf_deficit,
        spectral_dist=spec_dist,crest=inp_crest,src_br=src_br,
        band_snr=band_snr,mds=mds,has_ringing=has_ringing,
        rolloff_hz=br_rolloff,quality_label=quality_label
    )

    L(f"\n  MDS={mds:.1f}/100 → {quality_label}")
    L(f"  Crest={inp_crest:.2f} LRA={inp_lra:.2f} BR={src_br//1000}kbps"
      f" Ringing={'✓' if has_ringing else '✗'}")

    # ── v8.4: Source Tier Detection ──────────────────────────────────────────
    L(f"\n[٢ᵇ] تصنيف جودة المصدر v8.4 (SourceTierDetector)...")
    tier_profile = build_source_tier_profile(
        audio        = inp,
        inp_b        = inp_b,
        src_br       = src_br,
        snr_db       = snr_global,
        inp_lra      = inp_lra,
        ref_lra_clip = ref_fp.lra_clip,
        sr           = SR,
    )
    L(f"  ✦ Tier     = {tier_profile.tier}")
    L(f"  ✦ cutoff   = {tier_profile.input_cutoff_hz:.0f}Hz"
      f"  noise={tier_profile.noise_type}"
      f"  clip={tier_profile.clip_tier}({tier_profile.clip_ratio*100:.1f}%)")
    L(f"  ✦ Routing  : bias≤{tier_profile.bias_cutoff_hz:.0f}Hz"
      f"  eq_scale={tier_profile.eq_ramp_scale:.2f}x"
      f"  NR={'إلزامي' if tier_profile.nr_mandatory else 'اختياري'}"
      f"  LRA_expand={'✓' if tier_profile.lra_expand_gate else '✗ (AGC collapse)'}")
    L(f"  ✦ Ceiling  : Crest≤{tier_profile.achievable_crest:.2f}"
      f"  LRA≤{tier_profile.achievable_lra:.2f}"
      f"  LUFS≥{tier_profile.achievable_lufs:.2f}")

    # ── v8.6: Silence floor measurement ─────────────────────────────────────────
    L(f"\n[٢ᶜ] v8.6 — قياس أرضية الصمت (SilenceProfile)...")
    # v8.7: Sibilant smear diagnosis (before any processing)
    _smear_score, _smear_desc = detect_sibilant_smear(inp, SR)
    L(f"  [v8.7] smear_score={_smear_score}/10 ({_smear_desc}) -- v8.8 correction pending")

    L(f"\n[٢ᶜ] v8.6 -- قياس أرضية الصمت (SilenceProfile)...")
    if silence_profile.valid:
        L(f"  ✦ floor={silence_profile.floor_dbfs:.1f}dBFS"
          f"  noise_sfm={silence_profile.noise_sfm:.3f}"
          f"  frames={silence_profile.n_silence_frames}")
    else:
        L(f"  ✦ SilenceProfile: not enough silence frames — bypass")

    _pass0_applied = False
    _enhance_input = input_path
    if tier_profile.tier == 'TIER_DAMAGED' and silence_profile.valid:
        try:
            _tmp_p0 = os.path.join(_TMP, 'v86_pass0.wav')
            _p0_nr  = build_wiener_nr(silence_profile, 'TIER_DAMAGED')
            if _p0_nr:
                subprocess.run(['ffmpeg','-y','-i',input_path,'-af',_p0_nr,
                                '-ar','48000','-ac','2',_tmp_p0,'-loglevel','error'],
                               capture_output=True)
                if os.path.exists(_tmp_p0):
                    _enhance_input = _tmp_p0; _pass0_applied = True
                    L(f"  [v8.6] Pass 0 NR applied: {_p0_nr}")
        except Exception as _e0:
            L(f"  [v8.6] Pass 0 skipped: {_e0}")

    # v8.7: NR floor anchored to reference silence floor
    # Never push noise below the Sheikh's own 1425H recording silence floor.
    ref_nr_floor = float(ref_fp.silence_floor_db - 3.0)   # typically -76.0dBFS
    _hum_notch  = build_hum_notch(silence_profile)

    # v8.7: BroadbandStaticReducer pre-pass
    _bsr_applied = False
    if BroadbandStaticReducer.should_apply(
            silence_profile, tier_profile.noise_type,
            tier_profile.clip_tier, tier_profile.tier):
        _bsr_chain = BroadbandStaticReducer.build_chain(
            silence_profile, ref_nr_floor, tier_profile.tier)
        L(f"  [v8.7] BSR: {_bsr_chain}")
        _bsr_input, _bsr_applied = BroadbandStaticReducer.apply_and_verify(
            _enhance_input, _bsr_chain, skip_s, SR, L)
        if _bsr_applied:
            _enhance_input = _bsr_input
            L(f"  [v8.7] BSR applied -- input updated")
    else:
        _bsr_chain = ''

    _best_tracker  = BestPassTracker()
    _pass_metrics: List[PassMetrics] = []
    _nr_depth_cur  = 20
    _sib_snr_p1    = 0.0

    # ── STEP 2: MDS-Driven Processing ─────────────────────────────────────────
    L(f"\n[٣] Step 2a — SFM-Adaptive NR (v8.6)...")
    mds = compute_mds(snr_global, inp_sfm, inp_dr, hf_deficit, spec_dist, src_br,
                      ref_fp.sfm, ref_fp.dr, source_tier=tier_profile.tier)
    quality_label = mds_to_label(mds)
    damage.mds = mds; damage.quality_label = quality_label
    L(f"  [v8.5] MDS (tier-adjusted) = {mds:.1f}/100 -> {quality_label}"
      f"  [{tier_profile.tier} weights]")

    use_nr = tier_profile.nr_mandatory or ((src_br >= 96000) and (snr_global >= 8.0))
    nr_parts=build_nr_sfm_v86(damage,silence_profile,tier_profile.tier,_hum_notch,ref_nr_floor) if use_nr or has_ringing else (
        [f'lowpass=f={int(br_rolloff*0.97)}:poles=2'] if has_ringing else [])

    L(f"\n[٤] Step 2b — MDS-Calibrated Compand (v8 FIX: LRA delta صحيح)...")
    # v8 FIX #4: نمرر inp_lra للدالة
    compand_pts,makeup,intensity,calib=build_compand_mds_v86(damage,ref_fp,inp_lra,tier_profile.tier)
    lra_delta_actual=max(0.0,inp_lra-ref_fp.lra_clip)
    L(f"  Compand={intensity} Makeup=+{makeup:.1f}dB calib={calib:+.1f}dB"
      f" (LRA_delta={lra_delta_actual:.2f} | MDS={mds:.0f})")

    L(f"\n[٥] Step 2d -- Spectral Distance EQ (v8.7: post-NR basis)...")
    max_eq_db=4.0 if quality_label=='EXTREME' else 5.0 if quality_label=='VERY_POOR' else 6.0
    n_eq=12 if quality_label=='EXTREME' else 10
    # v8.7: measure spectrum AFTER NR to use as EQ basis.
    # PHYSICS: if NR removes 10dB at 6kHz, computing EQ from pre-NR spectrum
    # adds +2dB at 6kHz to a band that will be -10dB -- net -8dB vs target.
    _post_nr_b = measure_post_nr_spectrum(_enhance_input, nr_parts, skip_s, dur_s, SR)
    _eq_basis  = _post_nr_b if _post_nr_b else inp_b   # fallback: pre-NR spectrum
    L(f"  EQ basis: {'post-NR spectrum' if _post_nr_b else 'pre-NR spectrum (NR=none)'}")
    eq_nodes=optimize_eq(inp_b,ref_fp,n_nodes=n_eq,max_db=max_eq_db,
                         shape_only=(quality_label=='EXTREME'),hf_rolloff=hf_rolloff)

    warmth_pre=build_warmth_nodes(inp_b,ref_fp,hf_rolloff,
                                  post_compand=False,current_crest=inp_crest)
    eq_all=merge_eq(sorted(eq_nodes+warmth_pre,key=lambda x:x[0]),60.0)
    eq_all=[(f,float(np.clip(g,-max_eq_db,max_eq_db)),q) for f,g,q in eq_all]
    eq_final=[]
    for f0,g,q in eq_all:
        if f0>=hf_rolloff and g>0:
            if f0<hf_rolloff*1.5: eq_final.append((f0,min(-0.5,g*-0.3),q))
        else: eq_final.append((f0,g,q))
    eq_nodes_cur=eq_final
    L(f"  {len(eq_nodes_cur)} نقطة EQ (±{max_eq_db}dB)")

    inp_tilt=spectral_tilt(inp_b); tilt_corr=ref_fp.tilt_slope-inp_tilt
    # v8 FIX #1 + v8.4: bias_cutoff_hz من tier_profile
    # v8.45: also gate at ref codec cutoff — no boosts above ref's own HF ceiling
    bias_filter=build_bias_filter(
        hf_rolloff,
        min(tier_profile.bias_cutoff_hz, ref_fp.ref_codec_cutoff_hz)
    )
    L(f"  Bias: 250Hz→+{abs(-(-7.00)*BIAS_SCALE):.2f}dB↑ | "
      f"4kHz→{-(5.00*BIAS_SCALE):.2f}dB↓ | "
      f"8kHz→{-(8.00*BIAS_SCALE):.2f}dB↓ (v8 FIX)")

    # ── STEP 3: Do-No-Harm Convergence ────────────────────────────────────────
    L(f"\n{'─'*70}")
    L(f"  STEP 3 — Do-No-Harm Convergence (v8 — Single Compand + Single Limiter)")
    L(f"{'─'*70}")

    best_score=0.0; best_path=None

    for iteration in range(max_iterations):
        L(f"\n  ◆ تكرار {iteration+1}/{max_iterations}")

        # LUFS 7-point
        L(f"  [٦] LUFS 7-point Gaussian...")
        chain0=build_filter_chain(
            eq_nodes_cur,compand_pts,makeup,inp_hf,is_mono,0.0,
            nr_parts,bias_filter,[],intensity,inp_lra,damage,
            hf_rolloff,src_sr,ref_fp.lra_clip,tilt_corr
        ).replace('\n','').replace('    ','')

        l0=sample_lufs_7pt(input_path,total_s,n_ch,chain0)
        gain_needed=float(np.clip(TARGET['lufs']-l0-calib,-18,12))
        L(f"    LUFS_7pt={l0:.2f}  gain={gain_needed:+.2f}dB")

        # Pass 1 → WAV
        L(f"  [٧] Pass 1 → WAV (single compand, soft limiter)...")
        tmp_p1=os.path.join(_TMP,'v81_p1.wav')
        chain1=build_filter_chain(
            eq_nodes_cur,compand_pts,makeup,inp_hf,is_mono,gain_needed,
            nr_parts,bias_filter,[],intensity,inp_lra,damage,
            hf_rolloff,src_sr,ref_fp.lra_clip,tilt_corr
        ).replace('\n','').replace('    ','')

        r1=subprocess.run(['ffmpeg','-y','-i',_enhance_input,'-af',
                           chain1+',ebur128=peak=true',
                           '-ar','48000','-ac','2',tmp_p1,'-loglevel','info'],
                          capture_output=True,text=True)
        lufs_p1=-99.0
        for line in r1.stderr.split('\n'):
            s=line.strip()
            if s.startswith('I:') and 'LUFS' in s and 'LRA' not in s:
                try: lufs_p1=float(s.split('I:')[1].strip().split()[0]); break
                except: pass
        if lufs_p1==-99.0: lufs_p1=gain_needed+l0

        p1_a=load_audio(tmp_p1,skip=skip_s,duration=45)
        p1_b=third_octave(p1_a)
        p1_crest=crest_factor(p1_a)
        p1_m={'lufs':lufs_p1,'rms':rms_db(p1_a),'crest':p1_crest,'lra':lra_estimate(p1_a)}
        s1,_=quality_score(p1_b,ref_fp,p1_m,hf_rolloff,
                            tier_profile.tier,tier_profile.input_cutoff_hz)
        L(f"    LUFS={lufs_p1:.2f} RMS={p1_m['rms']:.2f} Crest={p1_crest:.2f}"
          f" LRA={p1_m['lra']:.2f} Score={s1}")
        _pm1=measure_pass_metrics(tmp_p1,ref_fp,1,None,skip_s,SR)
        _sib_snr_p1=_pm1.sibilant_snr
        _best_tracker.update(tmp_p1,_pm1); _pass_metrics.append(_pm1)

        # Pass 2 → WAV (spectral correction + warmth)
        L(f"  [٨] Pass 2 → WAV (Crest-aware spectral correction)...")
        lufs_corr=TARGET['lufs']-lufs_p1
        p1_adj={fc:v+lufs_corr for fc,v in p1_b.items()}
        max_c2=2.5 if quality_label=='EXTREME' else 3.0
        corr2=spectral_correction(p1_adj,ref_fp,hf_rolloff,max_c2,2,p1_crest)
        pw2=build_warmth_nodes(p1_adj,ref_fp,hf_rolloff,True,p1_crest)

        p2_parts=[f'volume={lufs_corr:.3f}dB']
        for f0,g,Q in corr2:
            p2_parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}')
        for f0,g,Q in pw2:
            p2_parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}')
        # v8 FIX #3: WAV وسيطة = limit ناعم جداً (يحفظ Crest)
        p2_parts.append('alimiter=limit=0.9997:level=false:attack=10:release=100')

        tmp_p2=os.path.join(_TMP,'v81_p2.wav')
        subprocess.run(['ffmpeg','-y','-i',tmp_p1,'-af',','.join(p2_parts),
                        '-ar','48000','-ac','2',tmp_p2,'-loglevel','error'],
                       capture_output=True)

        p2_a=load_audio(tmp_p2,skip=skip_s,duration=45)
        p2_b=third_octave(p2_a)
        p2_crest=crest_factor(p2_a); p2_lra=lra_estimate(p2_a); p2_rms=rms_db(p2_a)
        p2_m={'lufs':TARGET['lufs'],'rms':p2_rms,'crest':p2_crest,'lra':p2_lra}
        s2,_=quality_score(p2_b,ref_fp,p2_m,hf_rolloff,
                            tier_profile.tier,tier_profile.input_cutoff_hz)
        L(f"    RMS={p2_rms:.2f} Crest={p2_crest:.2f} LRA={p2_lra:.2f} Score={s2}")
        L(f"    Crest P1→P2: {p1_crest:.2f}→{p2_crest:.2f} (Δ={p1_crest-p2_crest:+.2f}LU)")
        _pm2=measure_pass_metrics(tmp_p2,ref_fp,2,_pm1,skip_s,SR)
        _nr_depth_cur=nr_sibilant_guard(_sib_snr_p1,_pm2.sibilant_snr,_nr_depth_cur)
        _best_tracker.update(tmp_p2,_pm2); _pass_metrics.append(_pm2)

        # ══════════════════════════════════════════════════════════════
        # v8 FIX #5: Quality Gate مع حارس Crest مستقل
        # ══════════════════════════════════════════════════════════════
        crest_collapsed=(p2_crest < p1_crest-1.5 and
                         p2_crest < TARGET['crest']-0.8)
        score_regressed=(s2 < s1-0.5)   # v8.7: tighter threshold (was 1.0)

        if crest_collapsed:
            # Full revert only -- half-intensity cannot recover Crest
            L(f"    ⚠ Quality Gate v8.7 [Crest collapsed] → full revert to P1")
            shutil.copy(tmp_p1,tmp_p2); p2_b=p1_b
            p2_crest=p1_crest; p2_lra=p1_m['lra']
            p2_rms=p1_m['rms']; p2_m=p1_m; s2=s1
        elif score_regressed:
            # v8.7: try half-intensity correction before full revert
            _half_corr2 = [(f0, round(g*0.5,3), q) for f0,g,q in corr2]
            _half_parts = [f'volume={lufs_corr:.3f}dB']
            for _f0,_g,_Q in _half_corr2:
                _half_parts.append(f'equalizer=f={_f0:.0f}:width_type=q:width={_Q}:g={_g}')
            _half_parts.append('alimiter=limit=0.9997:level=false:attack=10:release=100')
            _tmp_p2h = os.path.join(_TMP,'v87_p2h.wav')
            subprocess.run(['ffmpeg','-y','-i',tmp_p1,'-af',','.join(_half_parts),
                            '-ar','48000','-ac','2',_tmp_p2h,'-loglevel','error'],
                           capture_output=True)
            if os.path.exists(_tmp_p2h):
                _p2h_a = load_audio(_tmp_p2h,skip=skip_s,duration=dur_s)
                _p2h_b = third_octave(_p2h_a)
                _p2h_m = {'lufs':measure_lufs(_tmp_p2h),'rms':rms_db(_p2h_a),
                           'crest':crest_factor(_p2h_a),'lra':lra_estimate(_p2h_a)}
                _s2h,_ = quality_score(_p2h_b,ref_fp,_p2h_m,hf_rolloff,
                                       tier_profile.tier,tier_profile.input_cutoff_hz)
                if _s2h >= s1 - 0.3:
                    shutil.copy(_tmp_p2h,tmp_p2)
                    p2_b=_p2h_b; p2_crest=_p2h_m['crest']; p2_lra=_p2h_m['lra']
                    p2_rms=_p2h_m['rms']; p2_m=_p2h_m; s2=_s2h
                    L(f"    ✓ Gate v8.7: half-intensity rescued (s2={_s2h:.0f})")
                else:
                    shutil.copy(tmp_p1,tmp_p2); p2_b=p1_b
                    p2_crest=p1_crest; p2_lra=p1_m['lra']
                    p2_rms=p1_m['rms']; p2_m=p1_m; s2=s1
                    L(f"    ⚠ Gate v8.7: half-intensity failed (s2h={_s2h:.0f}) → full revert")
            else:
                shutil.copy(tmp_p1,tmp_p2); p2_b=p1_b
                p2_crest=p1_crest; p2_lra=p1_m['lra']
                p2_rms=p1_m['rms']; p2_m=p1_m; s2=s1
                L(f"    ⚠ Gate v8.7: half-intensity failed (ffmpeg error) → full revert")

        # Pass 3 → WAV (LRA + RMS feedback)
        L(f"  [٩] Pass 3 → WAV (LRA+RMS feedback)...")
        p3_parts=[]
        # v8.45: use phrase_lra_p50 as LRA target (phrase-level, not full-file average)
        # FORENSIC: phrase_lra_p50 measured at 3.34 LU (vs hardcoded 4.19 full-file)
        # using full-file 4.19 causes Pass 3 to over-expand — phrase target is more accurate
        lra_p3_target = ref_fp.phrase_lra_p50 if ref_fp.phrase_lra_p50 > 0.1 else ref_fp.lra
        lra_gap=lra_p3_target - p2_lra
        rms_gap=ref_fp.rms-p2_rms

        # v8: LRA gate هنا فقط | v8.4: lra_expand_gate يمنع التوسيع لـ TIER_DAMAGED
        if lra_gap>0.3 and p2_crest>TARGET['crest']-1.5 and tier_profile.lra_expand_gate:
            if   lra_gap<0.8: thr,ratio,rel=0.020,1.8,700
            elif lra_gap<1.5: thr,ratio,rel=0.026,2.2,580
            else:             thr,ratio,rel=0.032,2.6,450
            p3_parts.append(f'agate=threshold={thr:.3f}:ratio={ratio:.1f}'
                            f':attack=15:release={rel}:makeup=1.0:range=0.08')

        rms_leak=lra_gap*0.14 if lra_gap>0.3 else 0.0
        rms_adj=float(np.clip((rms_gap+rms_leak)*0.45,-1.2,1.2))
        if abs(rms_adj)>0.12:
            p3_parts.append(f'volume={rms_adj:.3f}dB')

        corr3=spectral_correction(p2_b,ref_fp,hf_rolloff,1.8,3,p2_crest)
        for f0,g,Q in corr3:
            p3_parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}')
        # v8 FIX #3: WAV وسيطة = limit ناعم
        p3_parts.append('alimiter=limit=0.9997:level=false:attack=10:release=100')

        tmp_p3=os.path.join(_TMP,'v81_p3.wav')
        if len(p3_parts)>1:
            subprocess.run(['ffmpeg','-y','-i',tmp_p2,'-af',','.join(p3_parts),
                            '-ar','48000','-ac','2',tmp_p3,'-loglevel','error'],
                           capture_output=True)
        else:
            shutil.copy(tmp_p2,tmp_p3)

        p3_a=load_audio(tmp_p3,skip=skip_s,duration=45)
        p3_b=third_octave(p3_a)
        p3_crest=crest_factor(p3_a); p3_lufs=measure_lufs(tmp_p3)
        p3_m={'lufs':p3_lufs,'rms':rms_db(p3_a),'crest':p3_crest,'lra':lra_estimate(p3_a)}
        s3,_=quality_score(p3_b,ref_fp,p3_m,hf_rolloff,
                            tier_profile.tier,tier_profile.input_cutoff_hz)

        if s3<s2-1.0:
            L(f"    ⚠ Quality Gate: P3({s3})<P2({s2}) → رجوع لـ P2")
            shutil.copy(tmp_p2,tmp_p3); p3_b=p2_b
            p3_lufs=TARGET['lufs']; p3_crest=p2_crest; s3=s2
        _pm3=measure_pass_metrics(tmp_p3,ref_fp,3,_pm2 if len(_pass_metrics)>=2 else None,skip_s,SR)
        _best_tracker.update(tmp_p3,_pm3); _pass_metrics.append(_pm3)
        _cont,_cont_reason=should_continue(_pass_metrics,tier_profile.tier)
        if _cont:
            c_extra=spectral_correction(p3_b,ref_fp,hf_rolloff,1.2,4,p3_crest)
            if c_extra:
                tmp_px=os.path.join(_TMP,'v86_px.wav')
                px_parts=[f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}' for f0,g,Q in c_extra]
                px_parts.append('alimiter=limit=0.9997:level=false:attack=10:release=100')
                subprocess.run(['ffmpeg','-y','-i',tmp_p3,'-af',','.join(px_parts),
                                '-ar','48000','-ac','2',tmp_px,'-loglevel','error'],capture_output=True)
                if os.path.exists(tmp_px):
                    shutil.copy(tmp_px,tmp_p3)
                    pmx=measure_pass_metrics(tmp_p3,ref_fp,4,_pm3,skip_s,SR)
                    _best_tracker.update(tmp_p3,pmx); _pass_metrics.append(pmx)

        # v8.6: BestPassTracker feeds Pass 4 input
        if (_best_tracker.best_composite_score > 0
                and _best_tracker.best_path
                and os.path.exists(_best_tracker.best_path)
                and _best_tracker.best_metrics
                and _best_tracker.best_metrics.crest > p3_crest + 0.15):
            shutil.copy(_best_tracker.best_path, tmp_p3)
            p3_crest = _best_tracker.best_metrics.crest
            p3_lufs  = _best_tracker.best_metrics.lufs

        # Pass 4 → MP3 (True Peak Compliance)
        # v8 FIX #3: alimiter=0.891 هنا فقط — التطبيق الوحيد الحقيقي
        lufs_trim=TARGET['lufs']-p3_lufs
        p4_parts=[]
        if abs(lufs_trim)>0.08: p4_parts.append(f'volume={lufs_trim:.3f}dB')
        if s3<93.0:
            c4=spectral_correction(p3_b,ref_fp,hf_rolloff,0.8,4,p3_crest)
            for f0,g,Q in c4:
                p4_parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}')
        # التطبيق الوحيد الحقيقي لـ True Peak limiter
        p4_parts.append('alimiter=limit=0.891:level=false:attack=1:release=15')

        tmp_out=os.path.join(_TMP,f'v81_out_{iteration}.mp3')
        subprocess.run(['ffmpeg','-y','-i',tmp_p3,'-af',','.join(p4_parts),
                        '-b:a','320k','-ar','48000','-ac','2',
                        tmp_out,'-loglevel','error'],capture_output=True)

        out_a=load_audio(tmp_out,skip=skip_s,duration=45)
        out_b_=third_octave(out_a)
        out_lufs=measure_lufs(tmp_out)
        out_m={'lufs':out_lufs,'rms':rms_db(out_a),
               'crest':crest_factor(out_a),'lra':lra_estimate(out_a)}
        fs,fbd=quality_score(out_b_,ref_fp,out_m,hf_rolloff,
                              tier_profile.tier,tier_profile.input_cutoff_hz)

        L(f"\n  ★ P1={s1}→P2={s2}→P3={s3}→Final={fs}/100")
        L(f"    LUFS={out_m['lufs']:.2f} RMS={out_m['rms']:.2f}"
          f" Crest={out_m['crest']:.2f} LRA={out_m['lra']:.2f}")

        if fs>best_score: best_score=fs; best_path=tmp_out
        if fs>=target_score: L(f"  ✅ هدف {target_score} محقق!"); break

        # Adaptive EQ
        if iteration<max_iterations-1:
            rv={fc:ref_fp.third_oct[fc] for fc in ref_fp.third_oct
                if fc in out_b_ and 100<=fc<=10000}
            ov={fc:out_b_[fc] for fc in rv}
            loff_i=float(np.mean([rv[fc]-ov[fc] for fc in rv]))
            sr_={fc:(rv[fc]-ov[fc])-loff_i for fc in rv}
            avg_se=float(np.mean(np.abs(list(sr_.values()))))
            # v8.1 PATCH #4: linear ramp | v8.4: × eq_ramp_scale (tier-gated)
            scale=min(0.45, max(0.08, 0.15 + (avg_se - 1.5) * 0.085))
            scale=max(0.04, scale * tier_profile.eq_ramp_scale)  # v8.4
            big=sorted([(fc,v) for fc,v in sr_.items() if abs(v)>2.5],
                       key=lambda x:-abs(x[1]))[:3]
            if big:
                corr=[(fc,round(v*scale,2),1.5) for fc,v in big]
                eq_nodes_cur=merge_eq(list(eq_nodes_cur)+corr,60.0)
                eq_nodes_cur=[(f,float(np.clip(g,-max_eq_db,max_eq_db)),q)
                              for f,g,q in eq_nodes_cur]
                L(f"  🔄 {len(corr)} EQ adaptive (avg_error={avg_se:.2f}dB, scale={scale:.3f} ramp)")

    # Finalize
    shutil.copy(best_path if best_path else tmp_out,output_path)
    if _input_tmp and os.path.exists(_input_tmp):
        try: os.remove(_input_tmp)
        except: pass

    fin_a=load_audio(output_path,skip=skip_s,duration=45)
    fin_b=third_octave(fin_a)
    fin_lufs=measure_lufs(output_path)
    fin_m={'lufs':fin_lufs,'rms':rms_db(fin_a),
           'crest':crest_factor(fin_a),'lra':lra_estimate(fin_a)}
    top_s,top_bd=quality_score(fin_b,ref_fp,fin_m,hf_rolloff,
                               tier_profile.tier,tier_profile.input_cutoff_hz)
    elapsed=time.time()-t0

    # v8.6: Recovery report
    _best_m = _best_tracker.best_metrics
    if _best_m:
        L(f"  [v8.6] RECOVERY  tier={tier_profile.tier}")
        L(f"    passes: {len(_pass_metrics)}  best_pass: {_best_m.pass_num} "
          f"(crest={_best_m.crest:.2f} eq_res={_best_m.eq_residual:.2f} "
          f"sib_snr={_best_m.sibilant_snr:.1f}dB)")
    L(f"\n{'═'*70}")
    L(f"  FINAL REPORT — v8.7 ({elapsed:.0f}s)")
    L(f"{'═'*70}")
    L(f"  {'المقياس':<18} {'المدخل':>8}  {'المخرج':>8}  {'الهدف 1425H':>12}")
    L(f"  {'─'*52}")
    L(f"  {'LUFS':<18} {'N/A':>8}  {fin_m['lufs']:>8.2f}  {TARGET['lufs']:>12.2f}")
    L(f"  {'RMS (dBFS)':<18} {inp_rms:>8.2f}  {fin_m['rms']:>8.2f}  {ref_fp.rms:>12.2f}")
    L(f"  {'Crest (LU)':<18} {inp_crest:>8.2f}  {fin_m['crest']:>8.2f}  {TARGET['crest']:>12.2f}")
    L(f"  {'LRA (LU)':<18} {inp_lra:>8.2f}  {fin_m['lra']:>8.2f}  {ref_fp.lra:>12.2f}")
    L(f"  {'MDS Score':<18} {mds:>8.1f}  {'→':>8}  {'0 (perfect)':>12}")

    # v8.4 SOURCE TIER line
    L(f"  [v8.4]  SOURCE TIER  {tier_profile.tier:<20}"
      f"  cutoff={tier_profile.input_cutoff_hz/1000:.1f}kHz"
      f"  noise={tier_profile.noise_type}"
      f"  clip={tier_profile.clip_tier}"
      f"  eq_scale={tier_profile.eq_ramp_scale:.2f}x"
      f"  bias_ceil={tier_profile.bias_cutoff_hz/1000:.1f}kHz")
    if tier_profile.tier != 'TIER_PRISTINE':
        L(f"          CEILING: Crest≤{tier_profile.achievable_crest:.2f}LU"
          f"  LRA≤{tier_profile.achievable_lra:.2f}LU"
          f"  LUFS≥{tier_profile.achievable_lufs:.2f}")
        if not tier_profile.lra_expand_gate:
            L(f"          ⚠ LRA expansion disabled — codec AGC destroyed dynamics")
        if tier_profile.noise_type not in ('none','unknown'):
            L(f"          NR applied: {tier_profile.noise_type}"
              f"  sfm_silence={tier_profile.sfm_silence:.2f}")

    bar='█'*int(top_s/5)+'░'*(20-int(top_s/5))
    L()
    L(f"  ★ {bar} {top_s}/100"
      f"  {'✅ EXCELLENT' if top_s>=96 else '✅ PASS' if top_s>=92 else '✓' if top_s>=88 else '⚠'}")
    # v8.5: show both tier-adjusted and absolute scores
    if top_bd.ceiling_reason:
        L(f"    [v8.5] score_tier={top_bd.score_tier}/100"
          f"  score_absolute={top_bd.score_absolute}/100"
          f"  (ceiling adjusted for {tier_profile.tier})")
        L(f"    ⓘ {top_bd.ceiling_reason}")
    else:
        L(f"    [v8.5] score_tier={top_bd.score_tier}/100"
          f"  score_absolute={top_bd.score_absolute}/100  (TIER_PRISTINE — no adjustment)")
    L(f"    Spectral:{top_bd.spectral} LUFS:{top_bd.lufs} Crest:{top_bd.crest}"
      f" LRA:{top_bd.lra} Warmth:{top_bd.warmth} HF:{top_bd.hf}")
    L(f"    خطأ طيفي:±{top_bd.avg_err}dB  MDS:{mds:.1f}/100({quality_label})")
    for n in top_bd.notes: L(f"    ⚠ {n}")

    # v8 Bug fixes summary in log
    L()
    L(f"  v8 Fixes Applied:")
    L(f"    ✓ BIAS 250Hz: +1.75dB boost (was -2.75dB cut in v7.6)")
    L(f"    ✓ BIAS 4kHz:  -1.25dB cut  (was +0.375dB boost in v7.6)")
    L(f"    ✓ BIAS 8kHz:  -2.00dB cut  (was +1.00dB boost in v7.6)")
    L(f"    ✓ No LRA stacking (single compand only)")
    L(f"    ✓ Single True Peak limiter in Pass 4 only")
    L(f"    ✓ LRA delta uses inp_lra vs lra_clip (was DR in v7.6)")
    L(f"  v8.1/v8.2 Patches Applied:")
    L(f"    ✓ REF_CACHE → ~/.tilawa_cache/ref_fp.v87.json (v8.7 version bump)")
    L(f"    ✓ REF_FILES → env / container_ref / legacy | --ref argparse fixed")
    L(f"    ✓ ALL /tmp/ → tempfile.gettempdir() (_TMP={_TMP})")
    L(f"    ✓ Adaptive EQ scale: linear ramp × tier eq_ramp_scale")
    L(f"    ✓ 64K_FLOOR label for honest Crest ceiling reporting")
    L(f"  v8.4 Source Tier Intelligence:")
    L(f"    ✓ SourceTierDetector: {tier_profile.tier} "
      f"cutoff={tier_profile.input_cutoff_hz:.0f}Hz "
      f"noise={tier_profile.noise_type}")
    L(f"    ✓ BIAS boost gated at {tier_profile.bias_cutoff_hz:.0f}Hz "
      f"(was always 20kHz)")
    L(f"    ✓ EQ scale={tier_profile.eq_ramp_scale:.2f}x "
      f"NR_mandatory={tier_profile.nr_mandatory} "
      f"LRA_expand={tier_profile.lra_expand_gate}")
    L(f"  v8.45 Deep Reference Model:")
    L(f"    ✓ Full-file spectral avg (was 8×30s clips — up to +16dB bias fixed)")
    L(f"    ✓ phrase_lra_p50={ref_fp.phrase_lra_p50:.2f}LU "
      f"p10={ref_fp.phrase_lra_p10:.2f} p90={ref_fp.phrase_lra_p90:.2f} "
      f"(Pass 3 target was hardcoded 4.19)")
    L(f"    ✓ silence_floor={ref_fp.silence_floor_db:.1f}dBFS "
      f"NR_ceiling={ref_fp.silence_floor_db - 3.0:.1f}dBFS")
    L(f"    ✓ ref_codec_cutoff={ref_fp.ref_codec_cutoff_hz:.0f}Hz "
      f"peak_dist={ref_fp.peak_distribution}")
    lra_p3_used = ref_fp.phrase_lra_p50 if ref_fp.phrase_lra_p50 > 0.1 else ref_fp.lra
    L(f"  [v8.45] REF MODEL  "
      f"n_refs={ref_fp.n_files}  "
      f"p50_lra={ref_fp.phrase_lra_p50:.2f}LU  "
      f"peak={ref_fp.peak_distribution}  "
      f"sil={ref_fp.silence_floor_db:.1f}dBFS  "
      f"cutoff={ref_fp.ref_codec_cutoff_hz:.0f}Hz")
    L(f"  v8.5 Tier-Adjusted Scoring:")
    L(f"    ✓ score_tier={top_bd.score_tier}/100  score_absolute={top_bd.score_absolute}/100")
    L(f"    ✓ compute_mds tier-weighted: {tier_profile.tier} "
      f"(SNR w={_V85_MDS_WEIGHTS[tier_profile.tier]['snr']:.2f}"
      f" SFM w={_V85_MDS_WEIGHTS[tier_profile.tier]['sfm']:.2f}"
      f" HF w={_V85_MDS_WEIGHTS[tier_profile.tier]['hf']:.2f})")
    L(f"    ✓ 64K_FLOOR hack removed — replaced by TierAdjustedScoring")
    if top_bd.ceiling_reason:
        L(f"    ✓ ceiling: {top_bd.ceiling_reason}")
    L(f"  [v8.5] TIER-SCORE  "
      f"tier={tier_profile.tier}  "
      f"score_tier={top_bd.score_tier}/100  "
      f"score_abs={top_bd.score_absolute}/100  "
      f"MDS={mds:.1f}")
    # v8.7 RESTORATION REPORT
    L(f"  v8.7 Coherent Pipeline:")
    L(f"    ✓ analysis_window: skip={skip_s}s dur={dur_s}s (total={total_s}s)")
    L(f"    ✓ ref_nr_floor={ref_nr_floor:.1f}dBFS "
      f"(ref_fp.silence_floor={ref_fp.silence_floor_db:.1f} − 3dB)")
    L(f"    ✓ EQ basis: {'post-NR spectrum' if _post_nr_b else 'pre-NR (no NR applied)'}")
    L(f"    ✓ HF: aexciter+treble (crystalizer removed -- sibilant artifact fix)")
    L(f"    ✓ BSR: {'applied' if _bsr_applied else 'skipped (gate: ' + tier_profile.noise_type + ')'}")
    L(f"    ✓ smear_score={_smear_score}/10 ({_smear_desc}) -- v8.8 correction pending")
    L(f"    ✓ peak_dist={getattr(ref_fp,'peak_distribution','uniform')} "
      f"→ attack x{'1.40' if getattr(ref_fp,'peak_distribution','uniform')=='front_loaded' else '0.85' if getattr(ref_fp,'peak_distribution','uniform')=='back_loaded' else '1.00'}")
    L(f"  [v8.7] RESTORATION  "
      f"bsr={'applied' if _bsr_applied else 'skipped'}  "
      f"smear={_smear_score}/10({_smear_desc})  "
      f"eq_basis={'post-NR' if _post_nr_b else 'pre-NR'}  "
      f"gate_retries={'half-intensity' if score_regressed else 'none'}")
    L(); L(f"  ✅ {output_path}"); L(f"{'═'*70}\n")

    return {
        'score':top_s,'breakdown':top_bd,'final_metrics':fin_m,
        'input_metrics':{'rms':inp_rms,'crest':inp_crest,'lra':inp_lra,
                         'snr':snr_global,'sfm':inp_sfm,'dr':inp_dr,'mds':mds},
        'quality_tier':quality_label,'mds':mds,
        'hf_rolloff_hz':hf_rolloff,'ref_lra':ref_fp.lra,
        'iterations':iteration+1,'log':log,'engine_version':'v8.6',
        'smear_score':_smear_score,'smear_desc':_smear_desc,
        'bsr_applied':_bsr_applied,'ref_nr_floor':ref_nr_floor,
        'eq_basis_source':('post_nr' if _post_nr_b else 'pre_nr'),
        'pass_count':len(_pass_metrics),
        'best_pass':(_best_tracker.best_metrics.pass_num if _best_tracker.best_metrics else 3),
        'score_absolute':top_bd.score_absolute,
        'score_tier':top_bd.score_tier,
        'ceiling_reason':top_bd.ceiling_reason,
        'source_tier':tier_profile.tier,
        'input_cutoff_hz':tier_profile.input_cutoff_hz,
        'noise_type':tier_profile.noise_type,
    }

def enhance_auto(input_path:str,output_path:str,
                 max_iterations:int=3,target_score:float=96.0) -> Dict:
    return enhance(input_path,output_path,max_iterations,target_score)

def process_batch(input_dir:str,output_dir:str) -> None:
    in_p=Path(input_dir); out_p=Path(output_dir); out_p.mkdir(parents=True,exist_ok=True)
    files=sorted([f for f in in_p.iterdir()
                  if f.suffix.lower() in {'.mp3','.wav','.m4a','.flac'}])
    if not files: print("لا توجد ملفات"); return
    scores=[]; results=[]
    for i,f in enumerate(files,1):
        dst=out_p/(f.stem+'_1425h_v81.mp3'); print(f"\n[{i}/{len(files)}] {f.name}")
        try:
            r=enhance_auto(str(f),str(dst))
            sc=r.get('score',0); scores.append(sc)
            results.append({'file':f.name,'score':sc,'status':'ok'}); print(f"  ✅ {sc}/100")
        except Exception as e:
            results.append({'file':f.name,'score':0,'status':'error','error':str(e)}); print(f"  ❌ {e}")
    avg=sum(scores)/len(scores) if scores else 0
    print(f"\n  Batch: {len(scores)}/{len(files)} avg={avg:.1f}/100")
    try:
        with open(out_p/'_batch_v81.json','w',encoding='utf-8') as jf:
            json.dump({'results':results,'avg_score':round(avg,1)},jf,ensure_ascii=False,indent=2)
    except: pass

def main() -> int:
    if not NUMPY_OK or not SCIPY_OK:
        print("pip install numpy scipy"); return 1
    p=argparse.ArgumentParser(description='Audio Enhancement Engine v8.7 — 1425H')
    p.add_argument('-i','--input');  p.add_argument('-o','--output')
    p.add_argument('--iterations',type=int,default=3)
    p.add_argument('--target',type=float,default=96.0)
    p.add_argument('--batch-in');   p.add_argument('--batch-out')
    p.add_argument('--serve',action='store_true')
    p.add_argument('--port',type=int,default=5000)
    p.add_argument('--clear-cache',action='store_true')
    p.add_argument('--ref', action='append', default=[],
                   metavar='REF_MP3',
                   help='Reference audio file path (may be repeated)')
    args=p.parse_args()
    if args.ref:
        valid_refs = [r for r in args.ref if os.path.exists(r)]
        if valid_refs:
            global REF_FILES
            REF_FILES = valid_refs
    if args.clear_cache:
        if os.path.exists(REF_CACHE): os.remove(REF_CACHE); print("✅ Cache v8 حُذف")
        return 0
    if args.serve:
        try: from flask import Flask,request,send_file,jsonify
        except: print("pip install flask"); return 1
        import threading, uuid as _uuid, re
        app=Flask(__name__); app.jobs={}
        @app.route('/')
        def index():
            return (Path(__file__).parent/'templates'/'index.html').read_text()
        @app.route('/upload',methods=['POST'])
        def upload():
            f=request.files.get('file')
            if not f: return jsonify(error='لم يُرسَل ملف'),400
            data=f.read()
            if len(data)>300*1024*1024: return jsonify(error='الحد الأقصى 300MB'),400
            jid=str(_uuid.uuid4())[:8]; home=Path(os.environ.get('HOME','/tmp'))
            (home/'uploads').mkdir(exist_ok=True); (home/'outputs').mkdir(exist_ok=True)
            ext=Path(f.filename or 'a.mp3').suffix or '.mp3'
            in_p=home/'uploads'/f'{jid}{ext}'; out_p=home/'outputs'/f'{jid}.mp3'
            in_p.write_bytes(data); stem=Path(f.filename or 'audio').stem
            app.jobs[jid]={'status':'processing','progress':5,'label':'جارٍ المعالجة...','new_log':[],
                           'in':str(in_p),'out':str(out_p),'filename':f'{stem}_v8.1.mp3'}
            def run(jid=jid,in_p=in_p,out_p=out_p):
                j=app.jobs[jid]
                try:
                    PHASES={'[١]':10,'[٢]':18,'[٣]':26,'[٤]':32,'[٥]':38,
                            '[٦]':50,'[٧]':62,'[٨]':74,'[٩]':86}
                    proc=subprocess.Popen(
                        ['python',__file__,'-i',str(in_p),'-o',str(out_p),'--iterations','3'],
                        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
                    for line in proc.stdout:
                        line=line.rstrip()
                        if not line: continue
                        j.setdefault('new_log',[]).append(line)
                        for tag,pct in PHASES.items():
                            if tag in line: j['progress']=pct; j['label']=line.strip()[:60]; break
                        if '★' in line:
                            m=re.search(r'([\d.]+)/100',line)
                            if m: j['score']=m.group(1)
                        for k,pat in [('crest',r'Crest'),('lra',r'LRA'),('rms',r'RMS')]:
                            if re.search(pat+r'\s*[=:]',line):
                                nums=re.findall(r'-?[\d.]+',line)
                                if len(nums)>=2: j.setdefault(k,nums[-2])
                    proc.wait()
                    if proc.returncode==0 and out_p.exists():
                        j.update({'status':'done','progress':100,'label':'اكتملت'})
                    else:
                        j.update({'status':'error','error':'فشلت المعالجة'})
                except Exception as e:
                    j.update({'status':'error','error':str(e)})
                finally:
                    try: in_p.unlink()
                    except: pass
            threading.Thread(target=run,daemon=True).start()
            return jsonify(job_id=jid)
        @app.route('/status/<jid>')
        def status(jid):
            j=app.jobs.get(jid)
            if not j: return jsonify(error='not found'),404
            r={'status':j['status'],'progress':j['progress'],
               'label':j.get('label',''),'log':j.pop('new_log',[])}
            if j['status']=='done':
                for k in ['score','crest','lra','rms','filename']: r[k]=j.get(k)
                r['job_id']=jid
            if j['status']=='error': r['error']=j.get('error','خطأ')
            return jsonify(r)
        @app.route('/download/<jid>')
        def download(jid):
            j=app.jobs.get(jid)
            if not j or not Path(j['out']).exists(): return 'Not found',404
            return send_file(j['out'],as_attachment=True,
                           download_name=j.get('filename','v8.1.mp3'))
        print(f"\n  محسّن التلاوة v8.1 — http://localhost:{args.port}\n")
        app.run(host='0.0.0.0',port=args.port,debug=False,threaded=True)
        return 0
    if args.batch_in and args.batch_out:
        process_batch(args.batch_in,args.batch_out); return 0
    if not args.input or not args.output:
        p.print_help(); return 1
    try:
        r=enhance_auto(args.input,args.output,args.iterations,args.target)
        print(f"\n  ★ {r['score']}/100  MDS={r['mds']:.0f}  ✅ {args.output}")
        return 0 if r['score']>=85 else 1
    except Exception as e:
        print(f"❌ {e}"); return 1

if __name__=='__main__':
    sys.exit(main())
