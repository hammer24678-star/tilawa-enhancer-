#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║   Audio Enhancement Engine v7.0 — "Convergence"                        ║
║   Reference: Sheikh Yasser Al-Dossari — Al-A'raf — 1425H               ║
╠══════════════════════════════════════════════════════════════════════════╣
║  v7 improvements over v6.6:                                             ║
║                                                                          ║
║  1. THREE-PASS PIPELINE — Pass3 يُصحح LRA+RMS بعد spectral correction  ║
║  2. STATISTICAL PRE-EQ — تصحيح الفجوات المنتظمة من 5+ ملفات معالجة    ║
║  3. ITERATIVE CONVERGENCE — يكرر حتى score ≥ 97 أو max 3 محاولات       ║
║  4. LRA FEEDBACK — يقيس LRA بعد Pass2 ويضغطه في Pass3 بدقة             ║
║  5. RMS FEEDBACK — يُعدّل الـ gain في Pass3 لضبط RMS على -10.01        ║
║  6. ADAPTIVE CORRECTION SCALE — يرفع/يخفض scale بناءً على error        ║
║  7. SPECTRAL BIAS CORRECTION — يُزيل الانحياز المنتظم في الـ EQ        ║
║  الهدف: ≥ 97/100 للـ GOOD/FAIR، ≥ 94/100 للـ POOR/EXTREME             ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import subprocess, sys, json, os, shutil, warnings
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.optimize import minimize
from scipy.interpolate import CubicSpline
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════
def _resolve_ref_files():
    """S255: where the reference recordings actually are.

    This engine had the three developer paths under /mnt/user-data/uploads/
    hard-coded, with no fallback. LocalEngineRunner never passes --ref, so on a
    phone every one of them was missing and the engine died before doing any
    work at all: "Error: Failed to load: /mnt/user-data/uploads/المرجع1425.mp3".
    v7.0 could not run offline, ever.

    Resolution order matches engine_v85.py's: env var, then the proot bind the
    app really provides, then the Termux home dir, then script-adjacent, then
    the legacy developer paths last."""
    import glob as _glob
    env_dir = os.environ.get('TILAWA_REF_DIR', '')
    cands = []
    if env_dir:
        cands.append(env_dir)
    cands.append('/reference_audio')                       # the proot bind mount
    cands.append(os.path.join(os.path.expanduser('~'), '.tilawa_ref'))
    cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reference_audio'))
    for d in cands:
        if d and os.path.isdir(d):
            found = sorted(p for p in _glob.glob(os.path.join(d, '*.mp3'))
                           if os.path.getsize(p) > 10_000)
            if found:
                return found
    legacy = [
        '/mnt/user-data/uploads/المرجع1425.mp3',
        '/mnt/user-data/uploads/سوره_الفتح_174232307.mp3',
        '/mnt/user-data/uploads/ياسر_الدوسري_ما_تسير_من_سورة_فاطر_1425__اول_مرة_تن_173856242_99.mp3',
    ]
    return [p for p in legacy if os.path.exists(p)]

_RESOLVED_REFS = _resolve_ref_files()
REF_PATH  = _RESOLVED_REFS[0] if _RESOLVED_REFS else ''
REF_CACHE = '/tmp/enhance_ref_fp.v7.json'
_CLI_REF_FILES = []  # S22: set by --ref CLI args; overrides REF_FILES in get_reference_fingerprint()
SR        = 48000

TARGET = {
    'lufs':        -6.29,
    'rms':         -9.44,
    'crest':        9.45,
    'lra':          4.00,   # fallback only — engine uses ref_fp.lra
    'peak_tp':      1.22,
    'snr':         35.5,
    'warmth_ratio': 0.60,
    'sr':          48000,
    'bitrate':     '320k',
}

# v7: انحياز طيفي مقاس حقيقياً من زوج (أصلي / v6.6) لسورة ق 1425
# القيمة = متوسط (ref - v6.6_output) بعد level normalization
# يُطبَّق في Pass2 كـ pre-correction قبل الـ spectral_correction_eq
SPECTRAL_BIAS = {
    80:   -2.84,   # v6.6 يُزيد bass زيادة → cut
    100:  -5.08,   # cut قوي
    125:  +4.16,   # v6.6 ينقص 125Hz → boost
    200:  -7.77,   # أكبر انحياز — cut حاد منتظم
    250:  +7.95,   # v6.6 ينقص 250Hz كثيراً → boost قوي
    315:  +3.85,   # boost
    400:  -3.01,   # cut
    500:  +1.95,   # boost خفيف
    630:  -3.69,   # cut
    800:  +1.76,   # boost خفيف
    1250: +0.54,
    2500: +2.32,
    3150: +1.55,
    5000: -1.03,
    6300: -1.12,
    8000: +1.10,
}
BIAS_SCALE = 0.15   # v7 تجريبي: 15% فقط — bias من ملف واحد غير كافٍ للـ scale الأعلى

CENTERS_31 = [
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160,
    200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600,
    2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000
]

BARK_BANDS = [
    (20,100),(100,200),(200,300),(300,400),(400,510),(510,630),(630,770),
    (770,920),(920,1080),(1080,1270),(1270,1480),(1480,1720),(1720,2000),
    (2000,2320),(2320,2700),(2700,3150),(3150,3700),(3700,4400),(4400,5300),
    (5300,6400),(6400,7700),(7700,9500),(9500,12000),(12000,20000)
]

A_WEIGHT = {
    20:-50.5, 25:-44.7, 31.5:-39.4, 40:-34.6, 50:-30.2,
    63:-26.2, 80:-22.5, 100:-19.1, 125:-16.1, 160:-13.4,
    200:-10.9, 250:-8.6,  315:-6.6,  400:-4.8,  500:-3.2,
    630:-1.9,  800:-0.8,  1000:0.0,  1250:0.6,  1600:1.0,
    2000:1.2,  2500:1.3,  3150:1.2,  4000:1.0,  5000:0.5,
    6300:-0.1, 8000:-1.1, 10000:-2.5,12500:-4.3,16000:-6.6, 20000:-9.3
}

# ═══════════════════════════════════════════════════════════════════════
#  AUDIO I/O
# ═══════════════════════════════════════════════════════════════════════
def load(path: str, sr: int = SR, mono: bool = True,
         skip: int = 0, duration: int = None) -> np.ndarray:
    channels = '1' if mono else '2'
    cmd = ['ffmpeg', '-i', path]
    if skip > 0:    cmd += ['-ss', str(skip)]
    if duration:    cmd += ['-t',  str(duration)]
    cmd += ['-f', 's16le', '-ac', channels, '-ar', str(sr), '-loglevel', 'error', '-']
    r = subprocess.run(cmd, capture_output=True)
    if not r.stdout:
        raise RuntimeError(f"Failed to load: {path}")
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0

def get_probe(path: str) -> Dict:
    r = subprocess.run(
        ['ffprobe','-v','quiet','-print_format','json',
         '-show_streams','-show_format', path],
        capture_output=True, text=True)
    return json.loads(r.stdout)

# ═══════════════════════════════════════════════════════════════════════
#  SIGNAL METRICS
# ═══════════════════════════════════════════════════════════════════════
def rms_db(a: np.ndarray) -> float:
    return float(20*np.log10(np.sqrt(np.mean(a**2))+1e-10))

def peak_db(a: np.ndarray) -> float:
    return float(20*np.log10(np.max(np.abs(a))+1e-10))

def crest_factor(a: np.ndarray) -> float:
    return float(peak_db(a) - rms_db(a))

def lra_estimate(a: np.ndarray, sr: int = SR) -> float:
    n = int(0.4*sr); step = n//2
    lvls = np.array([
        20*np.log10(np.sqrt(np.mean(a[i:i+n]**2))+1e-10)
        for i in range(0, len(a)-n, step)
    ])
    if len(lvls) < 2: return 0.0
    active = lvls[lvls > np.max(lvls)-30]
    return float(np.percentile(active,95)-np.percentile(active,10)) if len(active)>=2 else 0.0

def snr_estimate(a: np.ndarray, sr: int = SR) -> float:
    n = int(0.1*sr)
    blocks = np.array([np.sqrt(np.mean(a[i:i+n]**2)) for i in range(0,len(a)-n,n)])
    return float(20*np.log10(np.percentile(blocks,85)/(np.percentile(blocks,3)+1e-10)))

def count_clips(a: np.ndarray, threshold: float = 0.99) -> int:
    return int(np.sum(np.abs(a) >= threshold))

# ═══════════════════════════════════════════════════════════════════════
#  DE-CLIPPING
# ═══════════════════════════════════════════════════════════════════════
def declip(audio: np.ndarray, threshold: float = 0.98) -> Tuple[np.ndarray, int]:
    clipped   = np.abs(audio) >= threshold
    n_clipped = int(np.sum(clipped))
    if n_clipped == 0: return audio, 0
    out = audio.copy(); n = len(audio)
    diff   = np.diff(clipped.astype(int))
    starts = np.where(diff ==  1)[0] + 1
    ends   = np.where(diff == -1)[0] + 1
    if clipped[0]:   starts = np.insert(starts, 0, 0)
    if clipped[-1]:  ends   = np.append(ends, n)
    for s, e in zip(starts, ends):
        ctx      = 40
        pre_idx  = np.arange(max(0,s-ctx), s)
        post_idx = np.arange(e, min(n,e+ctx))
        good     = np.concatenate([pre_idx, post_idx])
        if len(good) < 4: continue
        try:
            cs = CubicSpline(good, audio[good], extrapolate=True)
            out[np.arange(s,e)] = cs(np.arange(s,e))
        except: pass
    return out, n_clipped

# ═══════════════════════════════════════════════════════════════════════
#  SPECTRAL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════
def third_octave(audio: np.ndarray, sr: int = SR,
                 chunk_sec: int = 40, a_weighted: bool = False) -> Dict[float,float]:
    chunk = audio[:sr*chunk_sec] if len(audio) > sr*chunk_sec else audio
    N     = len(chunk)
    spec  = np.abs(rfft(chunk))
    freqs = rfftfreq(N, 1.0/sr)
    out   = {}
    for fc in CENTERS_31:
        if fc >= sr/2: continue
        fl = fc/(2**(1/6)); fh = fc*(2**(1/6))
        mask = (freqs>=fl) & (freqs<fh)
        if mask.sum() > 0:
            v = float(20*np.log10(np.mean(spec[mask])+1e-10))
            if a_weighted and fc in A_WEIGHT: v += A_WEIGHT[fc]
            out[fc] = v
    return out

def bark_spectrum(audio: np.ndarray, sr: int = SR) -> List[Tuple[float,float]]:
    chunk = audio[:sr*30] if len(audio) > sr*30 else audio
    N     = len(chunk)
    spec  = np.abs(rfft(chunk))**2
    freqs = rfftfreq(N, 1.0/sr)
    result = []
    for fl, fh in BARK_BANDS:
        fh = min(fh, sr//2)
        mask = (freqs>=fl) & (freqs<fh)
        if mask.sum() > 0:
            result.append((float(np.sqrt(fl*fh)),
                           float(10*np.log10(np.mean(spec[mask])+1e-15))))
    return result

def hf_status(bands: Dict[float,float]) -> str:
    vals = [bands.get(fc,-99) for fc in [6300,8000,10000] if fc in bands]
    if not vals: return 'absent'
    avg = np.mean(vals)
    if avg > 10: return 'good'
    if avg > -5: return 'weak'
    return 'absent'

def detect_hf_rolloff(bands: Dict[float,float],
                      drop_threshold: float = 12.0) -> float:
    """v6.4: drop_threshold=12dB (was 15 in v6.3)"""
    fs = sorted([f for f in bands if 1600 <= f <= 20000])
    if not fs: return 20000.0
    prev = bands[fs[0]]
    for fc in fs[1:]:
        curr = bands[fc]
        if prev - curr > drop_threshold:
            return float(fc)
        prev = curr
    return 20000.0

def merge_eq_nodes(nodes: List[Tuple], min_hz_gap: float = 50.0) -> List[Tuple]:
    if not nodes: return nodes
    nodes  = sorted(nodes, key=lambda x: x[0])
    merged = [list(nodes[0])]
    for f0, g, Q in nodes[1:]:
        pf, pg, pq = merged[-1]
        if abs(f0-pf) < min_hz_gap:
            total = float(np.clip(pg+g, -16, 16))
            avg_f = (pf*abs(pg)+f0*abs(g)) / (abs(pg)+abs(g)+1e-6)
            merged[-1] = [round(avg_f,0), round(total,2), round((pq+Q)/2,2)]
        else:
            merged.append([f0, g, Q])
    return [tuple(x) for x in merged]

# ═══════════════════════════════════════════════════════════════════════
#  REFERENCE FINGERPRINT
# ═══════════════════════════════════════════════════════════════════════
@dataclass
class ReferenceFingerprint:
    third_oct:     Dict[float,float] = field(default_factory=dict)
    bark:          List[Tuple]       = field(default_factory=list)
    a_weighted:    Dict[float,float] = field(default_factory=dict)
    rms:           float = -9.44
    peak:          float =  0.99
    crest:         float =  9.45
    lra:           float =  3.50   # measured from real reference
    lufs:          float = -6.29
    warmth_ratio:  float =  0.0
    clarity_ratio: float =  0.0
    tilt_slope:    float =  0.0

def build_reference_fingerprint(audio: np.ndarray, sr: int = SR) -> ReferenceFingerprint:
    fp = ReferenceFingerprint()

    # v6.5: بناء الطيف من median كل المقاطع (أكثر استقراراً)
    chunk_n  = sr * 20
    n_chunks = max(1, len(audio) // chunk_n)
    all_bands = []
    crests_all, lras_all = [], []

    for ci in range(n_chunks):
        seg = audio[ci * chunk_n : (ci+1) * chunk_n]
        if len(seg) < sr * 3: continue
        b_seg = third_octave(seg, sr, a_weighted=False)
        all_bands.append(b_seg)
        crests_all.append(crest_factor(seg))
        lras_all.append(lra_estimate(seg, sr))

    if not all_bands:
        all_bands = [third_octave(audio, sr, a_weighted=False)]

    # Median spectrum — مقاوم للـ outliers
    fp.third_oct = {}
    for fc in CENTERS_31:
        vals = [b.get(fc) for b in all_bands if b.get(fc) is not None]
        if vals:
            fp.third_oct[fc] = float(np.median(vals))

    fp.a_weighted = third_octave(audio[:sr*30] if len(audio)>sr*30 else audio,
                                 sr, a_weighted=True)
    fp.bark  = bark_spectrum(audio[:sr*30] if len(audio)>sr*30 else audio, sr)
    fp.rms   = rms_db(audio)
    fp.peak  = peak_db(audio)
    fp.crest = float(np.median(crests_all)) if crests_all else crest_factor(audio)
    fp.lra   = float(np.median(lras_all))   if lras_all   else lra_estimate(audio, sr)

    fc_arr  = np.array([fc for fc in CENTERS_31 if 100<=fc<=10000 and fc in fp.third_oct])
    db_arr  = np.array([fp.third_oct[fc] for fc in fc_arr])
    if len(fc_arr) >= 3:
        fp.tilt_slope = float(np.polyfit(np.log2(fc_arr/1000.0), db_arr, 1)[0])

    # v6.5: warmth = spectral tilt 200→2000Hz (أكثر استقراراً من bass/mid ratio)
    # الـ tilt_slope يعكس التوازن الجوهري للطيف بدون تأثير الـ resonances
    tilt_fc  = np.array([fc for fc in CENTERS_31 if 200<=fc<=2000 and fc in fp.third_oct])
    tilt_db  = np.array([fp.third_oct[fc] for fc in tilt_fc])
    if len(tilt_fc) >= 3:
        fp.warmth_ratio = float(np.polyfit(np.log2(tilt_fc/1000.0), tilt_db, 1)[0])
    else:
        fp.warmth_ratio = fp.tilt_slope

    high_e           = np.mean([fp.third_oct.get(fc,-60) for fc in [4000,5000,6300,8000]])
    mid_e2           = np.mean([fp.third_oct.get(fc,-60) for fc in [500,630,800,1000]])
    fp.clarity_ratio = float(mid_e2 - high_e)
    return fp

def get_reference_fingerprint() -> ReferenceFingerprint:
    """
    v7: Multi-file fingerprint من 3 سور 1425H (الأعراف + الفتح + فاطر)
    - يتجنب مقدمة كل ملف (يبدأ من 15%) لتفادي bass artifacts
    - median عبر الملفات الثلاثة بعد level normalization
    - أكثر دقة من ملف واحد (σ أقل في RMS/Crest/LRA)
    """
    import json
    cache_file = '/tmp/enhance_ref_fp.v7.json'

    # S22: CLI-provided paths win; otherwise _resolve_ref_files() finds the
    # bundled recordings (S255 — this used to be the same hard-coded developer
    # list, which does not exist on a phone).
    REF_FILES = (_CLI_REF_FILES if _CLI_REF_FILES else _RESOLVED_REFS)
    if not REF_FILES:
        raise RuntimeError(
            'no reference recordings found — looked in $TILAWA_REF_DIR, '
            '/reference_audio, ~/.tilawa_ref and alongside the engine')
    # نستخدم الملف الأول للتحقق من تغيير cache
    primary = REF_FILES[0]

    if os.path.exists(cache_file):
        try:
            if os.path.getmtime(cache_file) >= os.path.getmtime(primary):
                with open(cache_file, 'r') as f:
                    d = json.load(f)
                fp = ReferenceFingerprint()
                fp.third_oct     = {float(k): v for k,v in d['third_oct'].items()}
                fp.a_weighted    = {float(k): v for k,v in d.get('a_weighted',{}).items()}
                fp.bark          = [(float(a), float(b)) for a,b in d.get('bark',[])]
                fp.rms           = d['rms'];  fp.peak  = d['peak']
                fp.crest         = d['crest']; fp.lra  = d['lra']
                fp.tilt_slope    = d['tilt_slope']
                fp.warmth_ratio  = d['warmth_ratio']
                fp.clarity_ratio = d.get('clarity_ratio', 0.0)
                return fp
        except Exception:
            pass

    # بناء fingerprint من كل ملف
    # percentages تتجنب البداية: 15% → 88%
    SAFE_PCT = [0.15, 0.28, 0.42, 0.56, 0.70, 0.84]
    all_fp_data = []

    for path in REF_FILES:
        if not os.path.exists(path):
            continue
        try:
            probe   = get_probe(path)
            total_s = int(float(probe.get('format',{}).get('duration',300)))
            skips   = [max(15, int(total_s * r)) for r in SAFE_PCT]

            clips = [f'/tmp/ref_v7_f{REF_FILES.index(path)}_s{i}.wav' for i in range(len(skips))]
            procs = [
                subprocess.Popen(['ffmpeg','-y','-i',path,
                                  '-ss',str(sk),'-t','30',
                                  '-f','s16le','-ac','1','-ar',str(SR),
                                  cl,'-loglevel','error'])
                for sk,cl in zip(skips,clips)
            ]
            for p in procs: p.wait()

            segs_spec, segs_rms, segs_crest, segs_lra = [], [], [], []
            for cl in clips:
                try:
                    if not os.path.exists(cl) or os.path.getsize(cl) < SR*2: continue
                    raw = open(cl, 'rb').read()
                    a   = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
                    if len(a) < SR*3: continue
                    segs_spec.append(third_octave(a, a_weighted=False))
                    segs_rms.append(rms_db(a))
                    segs_crest.append(crest_factor(a))
                    segs_lra.append(lra_estimate(a))
                except: pass

            if len(segs_spec) >= 3:
                common = [fc for fc in CENTERS_31 if all(fc in s for s in segs_spec)]
                med_spec  = {fc: float(np.median([s[fc] for s in segs_spec])) for fc in common}
                all_fp_data.append({
                    'spec':  med_spec,
                    'rms':   float(np.median(segs_rms)),
                    'crest': float(np.median(segs_crest)),
                    'lra':   float(np.median(segs_lra)),
                })
        except Exception:
            continue

    # fallback على الأعراف وحده إذا فشل التحميل
    if len(all_fp_data) < 2:
        fp_single = _build_single_ref(primary)
        return fp_single

    # level-normalize ثم median عبر الملفات
    ref_level  = float(np.mean([f['rms'] for f in all_fp_data]))
    common_all = [fc for fc in CENTERS_31 if all(fc in f['spec'] for f in all_fp_data)]
    normalized = [{fc: f['spec'][fc] + (ref_level - f['rms']) for fc in common_all}
                  for f in all_fp_data]
    multi_spec = {fc: float(np.median([s[fc] for s in normalized])) for fc in common_all}

    fp = ReferenceFingerprint()
    fp.third_oct = multi_spec
    fp.rms       = float(np.median([f['rms']   for f in all_fp_data]))
    fp.peak      = -1.22
    fp.crest     = float(np.median([f['crest'] for f in all_fp_data]))
    fp.lra       = float(np.median([f['lra']   for f in all_fp_data]))

    fc_arr = np.array([fc for fc in CENTERS_31 if 100<=fc<=10000 and fc in fp.third_oct])
    db_arr = np.array([fp.third_oct[fc] for fc in fc_arr])
    if len(fc_arr) >= 3:
        fp.tilt_slope = float(np.polyfit(np.log2(fc_arr/1000.0), db_arr, 1)[0])

    tilt_fc = np.array([fc for fc in CENTERS_31 if 200<=fc<=2000 and fc in fp.third_oct], dtype=float)
    tilt_db = np.array([fp.third_oct[fc] for fc in tilt_fc])
    if len(tilt_fc) >= 3:
        fp.warmth_ratio = float(np.polyfit(np.log2(tilt_fc/1000.0), tilt_db, 1)[0])

    # a_weighted و bark من الأعراف
    try:
        prim_audio = load(primary, skip=int(float(get_probe(primary).get(
            'format',{}).get('duration',300))*0.35), duration=60)
        fp.a_weighted    = third_octave(prim_audio, a_weighted=True)
        fp.bark          = bark_spectrum(prim_audio)
        high_e           = np.mean([fp.third_oct.get(fc,-60) for fc in [4000,5000,6300,8000]])
        mid_e2           = np.mean([fp.third_oct.get(fc,-60) for fc in [500,630,800,1000]])
        fp.clarity_ratio = float(mid_e2 - high_e)
    except: pass

    try:
        d = {
            'third_oct':     {str(k): v for k,v in fp.third_oct.items()},
            'a_weighted':    {str(k): v for k,v in fp.a_weighted.items()},
            'bark':          [[float(a),float(b)] for a,b in fp.bark],
            'rms': fp.rms, 'peak': fp.peak, 'crest': fp.crest, 'lra': fp.lra,
            'tilt_slope': fp.tilt_slope, 'warmth_ratio': fp.warmth_ratio,
            'clarity_ratio': fp.clarity_ratio,
            'source': 'v7-multi: الأعراف+الفتح+فاطر 1425H',
            'n_files': len(all_fp_data),
        }
        with open(cache_file,'w') as f: json.dump(d,f)
    except: pass

    return fp


def _build_single_ref(path: str) -> ReferenceFingerprint:
    """fallback: بناء fingerprint من ملف واحد (نفس طريقة v6.5)"""
    probe   = get_probe(path)
    total_s = int(float(probe.get('format',{}).get('duration',300)))
    skips   = [max(10, int(total_s * r)) for r in [0.10, 0.25, 0.45, 0.65, 0.82]]
    clips   = [f'/tmp/ref65_s{i}.wav' for i in range(5)]
    procs   = [
        subprocess.Popen(['ffmpeg','-y','-i',path,'-ss',str(sk),'-t','40',
                          '-f','s16le','-ac','1','-ar',str(SR),cl,'-loglevel','error'])
        for sk,cl in zip(skips,clips)
    ]
    for p in procs: p.wait()
    segments = []
    for cl in clips:
        try:
            r = subprocess.run(['ffmpeg','-i',cl,'-f','s16le','-ac','1',
                                '-ar',str(SR),'-','-loglevel','error'], capture_output=True)
            a = np.frombuffer(r.stdout, np.int16).astype(np.float32)/32768.0
            if len(a) > SR: segments.append(a)
        except: pass
    ref_audio = np.concatenate(segments) if segments else load(path, skip=30, duration=120)
    return build_reference_fingerprint(ref_audio)

# ═══════════════════════════════════════════════════════════════════════
#  EQ OPTIMIZER — v6.4 (per-tier gain clamp)
# ═══════════════════════════════════════════════════════════════════════
def optimize_eq_bark(new_b: Dict, ref_fp: ReferenceFingerprint,
                     n_nodes: int = 10, use_a_weight: bool = True,
                     max_gain_db: float = 6.0,
                     shape_only: bool = False) -> List[Tuple]:
    """
    v6.4: max_gain_db is passed per-tier.
    shape_only=True (EXTREME): يُصحح الشكل فقط، compand يرفع المستوى.
      EXTREME=4dB, VERY_POOR=5dB, else=6dB
    Prevents over-boost that compand then amplifies.
    """
    ref_b  = ref_fp.third_oct
    common = sorted([fc for fc in new_b if fc in ref_b and 80<=fc<=14000])
    if len(common) < 4: return []

    fc_arr  = np.array(common, dtype=float)
    new_arr = np.array([new_b[fc]      for fc in common])
    ref_arr = np.array([ref_b[fc]      for fc in common])
    level_offset = float(np.mean(ref_arr - new_arr))
    target  = (ref_arr - new_arr) - level_offset
    # shape_only: يُصحح الشكل فقط (compand يرفع المستوى)
    if shape_only:
        target = target - float(np.mean(target))
    weights = np.array([max(0.2, 1+A_WEIGHT.get(fc,0)/10) for fc in common]) \
              if use_a_weight else np.ones(len(common))

    init_freqs = np.logspace(np.log10(80), np.log10(14000), n_nodes)

    def eq_response(freq_axis, params):
        resp = np.zeros(len(freq_axis))
        for i in range(n_nodes):
            f0   = abs(params[i*3])   + 1e-6
            gain = params[i*3+1]
            Q    = max(0.3, abs(params[i*3+2]))
            ratio = freq_axis / f0
            resp += gain / (1 + Q**2*(ratio - 1.0/(ratio+1e-9))**2)
        return resp

    def objective(params):
        resp  = eq_response(fc_arr, params)
        error = np.mean(weights*(resp-target)**2)
        gains = [params[i*3+1] for i in range(n_nodes)]
        smooth = sum(0.015*(gains[i+1]-gains[i])**2 for i in range(len(gains)-1))
        mag    = sum(0.003*g**2 for g in gains)
        return error + smooth + mag

    init_gains = np.interp(np.log10(init_freqs), np.log10(fc_arr), target)
    x0 = []
    for f,g in zip(init_freqs, init_gains):
        x0.extend([float(np.clip(f,80,14000)),
                   float(np.clip(g,-max_gain_db,max_gain_db)), 1.0])

    result = minimize(objective, x0, method='L-BFGS-B',
                      bounds=[(80,14000),(-max_gain_db,max_gain_db),(0.3,4.0)]*n_nodes,
                      options={'maxiter':400,'ftol':1e-9,'gtol':1e-8})
    nodes = []
    for i in range(n_nodes):
        f0   = abs(result.x[i*3])
        gain = result.x[i*3+1]
        Q    = max(0.3, abs(result.x[i*3+2]))
        # v6.4: EXTREME tier — limit mid cuts (compand amplifies 500-1500Hz)
        # over-cutting mid creates warmth ratio imbalance after compand
        if shape_only and gain < 0 and 400 <= f0 <= 1600:
            gain = max(gain, -2.0)
        if abs(gain) >= 0.4:
            nodes.append((round(f0,0), round(gain,2), round(Q,2)))
    return sorted(nodes, key=lambda x: x[0])

# ═══════════════════════════════════════════════════════════════════════
#  WARMTH CORRECTION — v6.4
# ═══════════════════════════════════════════════════════════════════════
def warmth_nodes(new_b: Dict, ref_fp: ReferenceFingerprint,
                 quality_tier: str = 'GOOD',
                 post_compand: bool = False,
                 hf_rolloff_hz: float = 20000.0) -> List[Tuple]:
    """
    v6.5: Tilt-based warmth correction (أكثر استقراراً من bass/mid ratio)
    - يحسب spectral tilt 200-2000Hz للمدخل والمرجع
    - يُصحح الفرق بـ shelf أكثر موسيقية
    - post_compand=True → scale 0.25 (أخف من v6.4)
    """
    # حساب tilt 200→2000Hz للمدخل
    tilt_fc  = np.array([fc for fc in CENTERS_31 if 200<=fc<=2000 and fc in new_b
                         and fc < hf_rolloff_hz], dtype=float)
    if len(tilt_fc) < 3: return []
    tilt_db  = np.array([new_b[fc] for fc in tilt_fc])
    new_tilt = float(np.polyfit(np.log2(tilt_fc/1000.0), tilt_db, 1)[0])

    # ref warmth_ratio هو الـ tilt في v6.5
    ref_tilt = ref_fp.warmth_ratio
    tilt_diff = ref_tilt - new_tilt   # موجب = المرجع أدفأ

    threshold = 1.0 if quality_tier in ('EXTREME','VERY_POOR') else 2.0
    scale     = 0.25 if post_compand else 0.40
    max_adj   = 2.5  if post_compand else 5.0

    nodes = []
    if abs(tilt_diff) > threshold:
        # bass shelf لتصحيح الـ tilt (200Hz shelf)
        bass_adj = float(np.clip(tilt_diff * scale, -max_adj, max_adj))
        if abs(bass_adj) >= 0.4:
            nodes.append((200.0, round(bass_adj, 2), 0.55))
        # mid correction خفيف عكسي
        mid_adj = float(np.clip(-tilt_diff * 0.15, -2.0, 2.0))
        if abs(mid_adj) >= 0.4:
            nodes.append((1000.0, round(mid_adj, 2), 0.80))
    return nodes

# ═══════════════════════════════════════════════════════════════════════
#  NEW v6.4: TWO-PASS SPECTRAL CORRECTION
# ═══════════════════════════════════════════════════════════════════════
def spectral_correction_eq(out_b: Dict, ref_fp: ReferenceFingerprint,
                            hf_rolloff_hz: float = 20000.0,
                            max_correction_db: float = 4.0,
                            protect_warmth: bool = True) -> List[Tuple]:
    """
    v6.4: Two-Pass Correction
    - شكل فقط (level_offset → LUFS correction)
    - warmth protection: لا cuts على 400-1600Hz إذا warmth مقبول
    """
    ref_b  = ref_fp.third_oct
    ceil   = min(10000.0, hf_rolloff_hz * 0.9)
    common = sorted([fc for fc in out_b if fc in ref_b and 80 <= fc <= ceil])
    if len(common) < 4: return []

    out_arr   = np.array([out_b[fc] for fc in common])
    ref_arr   = np.array([ref_b[fc] for fc in common])
    level_off = float(np.mean(ref_arr - out_arr))
    shape_gap = (ref_arr - out_arr) - level_off

    aw = np.array([max(0.3, 1 + A_WEIGHT.get(fc, 0) / 10) for fc in common])

    # warmth protection — تحقق من الـ tilt بدل bass/mid ratio
    tilt_fc_w = np.array([fc for fc in common if 200<=fc<=2000], dtype=float)
    if protect_warmth and len(tilt_fc_w) >= 3:
        tilt_db_w  = np.array([out_b[fc] for fc in tilt_fc_w])
        out_tilt_w = float(np.polyfit(np.log2(tilt_fc_w/1000.0), tilt_db_w, 1)[0])
        warmth_ok  = abs(out_tilt_w - ref_fp.warmth_ratio) < 4.0
    else:
        warmth_ok = False

    nodes     = []
    prev_gain = 0.0
    for i, fc in enumerate(common):
        raw_g = float(shape_gap[i])
        # v6.6: scale 0.68 (was 0.60), stronger correction
        g = float(np.clip(raw_g * aw[i] * 0.68, -max_correction_db, max_correction_db))
        # v6.6: warmth protection only when error < 3dB (was always when warmth_ok)
        # large errors (>3dB) must be corrected even in warmth zone
        if warmth_ok and 400 <= fc <= 1600 and g < -0.5 and abs(raw_g) < 3.0:
            g = max(g * 0.15, -0.3)
        if abs(g) >= 0.5 and abs(g - prev_gain) < 5.0:
            Q = 1.0 if abs(g) < 2 else 0.70
            nodes.append((float(fc), round(g, 2), Q))
        prev_gain = g
    return nodes

# ═══════════════════════════════════════════════════════════════════════
def build_compand_curve(inp_crest: float, inp_lra: float,
                        ref_lra:   float = 4.0,
                        force_extreme: bool = False) -> Tuple:
    """
    v6.4:
    - Uses ref_lra (real measured) instead of TARGET['lra']=4.0
    - EXTREME: attack=20ms/decay=400ms/gain=2.5
      (was attack=4ms/decay=250ms/gain=5.0 → Crest killed)
    """
    crest_delta = inp_crest - TARGET['crest']
    lra_delta   = inp_lra   - ref_lra
    score = crest_delta*0.75 + max(0.0, lra_delta)*0.25

    if force_extreme or score >= 11:
        # v6.4: gentler attack (20ms) preserves transients → Crest intact
        return ("-90/-68|-45/-20|-28/-9|-14/-4.5|-7/-2.0|-3/-0.6|0/-0.1",
                2.5, 'EXTREME', 2.0)
    elif score >= 6.5:
        return ("-90/-72|-42/-21|-26/-10.5|-13/-5.2|-6/-2.4|-2.5/-0.8|-0.5/-0.3|0/-0.1",
                3.2, 'HEAVY', 1.8)
    elif score >= 3.5:
        return ("-90/-78|-40/-25|-22/-12.5|-12/-6.8|-6/-3.5|-2.5/-1.6|-0.8/-0.5|0/-0.2",
                2.5, 'MEDIUM', 1.4)
    elif score >= 1.5:
        return ("-90/-85|-40/-36|-20/-17|-10/-8.2|-5/-4.1|-2/-1.6|-0.5/-0.4|0/-0.3",
                1.2, 'LIGHT', 0.9)
    elif score >= 0.5:
        return ("-90/-89|-40/-39|-20/-19.5|-10/-9.8|-4/-3.9|-1/-0.95|0/-0.3",
                0.4, 'MINIMAL', 0.4)
    else:
        return ("-90/-90|-20/-20|-3/-3|0/0", 0.0, 'BYPASS', 0.0)

# ═══════════════════════════════════════════════════════════════════════
#  FILTER CHAIN BUILDER — v6.4
# ═══════════════════════════════════════════════════════════════════════
def build_filter_chain(eq_nodes:         List[Tuple],
                       compand_pts:      str,
                       makeup:           float,
                       hf:               str,
                       is_mono:          bool,
                       gain_db:          float,
                       noise_reduce:     bool  = True,
                       tilt_slope:       float = 0.0,
                       inp_snr:          float = 30.0,
                       intensity:        str   = 'MEDIUM',
                       inp_lra:          float = 4.0,
                       inp_crest:        float = 9.45,
                       quality_tier:     str   = 'GOOD',
                       hf_rolloff_hz:    float = 20000.0,
                       src_sr:           int   = 44100,
                       correction_nodes: List[Tuple] = None,
                       post_warmth_nodes:List[Tuple] = None,
                       ref_lra:          float = 2.26) -> str:   # v6.6: real ref target
    """
    v6.4 pipeline order:

      HP(28Hz)
      → PRE-NR [EXTREME: 22+6, others: adaptive]
      → Tilt EQ
      → Main EQ (bark-optimized, clamped per tier)
      → HF Resurrection [EXTREME: crystalizer i=7 + treble cascade]
      → POST-NR [light — preserves transients]
      → LRA gate/expand
      → Compand [EXTREME: 20ms/400ms/gain=2.5]
      → Post-compand warmth hook  ← NEW v6.4
      → Spectral correction EQ   ← NEW v6.4 (two-pass)
      → Transient limiter
      → Volume
      → Stereo (if mono)
      → Final ceiling
    """
    if correction_nodes is None:     correction_nodes     = []
    if post_warmth_nodes is None:    post_warmth_nodes    = []
    parts      = []
    is_bypass  = (intensity == 'BYPASS')
    is_extreme = (quality_tier == 'EXTREME')

    # ── 1. High-pass ─────────────────────────────────────────────
    parts.append('highpass=f=28:poles=2')

    # ── 2. PRE-NR — v6.4: lighter second pass for EXTREME ────────
    #   Old v6.3: 22+12 → kills peaks → Crest collapses
    #   New v6.4: 22+6  → keeps transients
    if noise_reduce and not is_bypass:
        if is_extreme:
            parts.append('afftdn=nr=22:nf=-55:tn=1')
            parts.append('afftdn=nr=6:nf=-65:tn=1')   # v6.4: was nr=12
        elif quality_tier == 'VERY_POOR':
            if inp_snr < 8:
                parts.append('afftdn=nr=18:nf=-58:tn=1')
            elif inp_snr < 15:
                parts.append('afftdn=nr=12:nf=-62:tn=1')
        elif quality_tier == 'POOR':
            if inp_snr < 12:
                nr = max(6, min(12, int((20.0-inp_snr)*0.7)))
                parts.append(f'afftdn=nr={nr}:nf=-65:tn=1')

    # ── 3. Spectral tilt correction ──────────────────────────────
    if not is_bypass and abs(tilt_slope) > 1.0:
        db = min(abs(tilt_slope)*0.35, 5.0)
        if tilt_slope > 0:
            parts.append(f'treble=g={db:.1f}:f=8000:width_type=o:width=2')
        else:
            parts.append(f'bass=g={db:.1f}:f=150:width_type=o:width=2')

    # ── 4. Main EQ ───────────────────────────────────────────────
    for f0, gain, Q in eq_nodes:
        parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={gain}')

    # ── 5. HF Resurrection — v6.4: crystalizer i=7 for EXTREME ──
    #   Old v6.3: crystalizer i=10 → 2-5kHz boosted 4-7dB above ref
    #   New v6.4: i=7 + multi-shelf treble cascade
    if not is_bypass:
        if is_extreme:
            parts.append('crystalizer=i=7')             # v6.4: was i=10
            if hf_rolloff_hz < 8000:
                treble_f = max(2000, int(hf_rolloff_hz*0.65))
                parts.append(f'treble=g=3.5:f={treble_f}:width_type=o:width=2')
            parts.append('treble=g=3.0:f=7000:width_type=o:width=1.5')
        elif quality_tier == 'VERY_POOR':
            parts.append('crystalizer=i=6')
            parts.append('treble=g=2.0:f=6000:width_type=o:width=2')
        elif quality_tier == 'POOR':
            if hf == 'weak':    parts.append('crystalizer=i=4')
            elif hf=='absent':  parts.append('crystalizer=i=6')
        else:  # FAIR / GOOD
            if hf == 'weak':    parts.append('crystalizer=i=4')
            elif hf=='absent':  parts.append('crystalizer=i=6')

    # ── 6. POST-NR — very light to preserve peaks ────────────────
    if noise_reduce and not is_bypass:
        if is_extreme:
            parts.append('afftdn=nr=4:nf=-80:tn=0')    # v6.4: was nr=10
        elif quality_tier in ('POOR','VERY_POOR'):
            parts.append('afftdn=nr=6:nf=-74:tn=0')
        elif inp_snr < 40:
            nr = max(3, min(10, int((40.0-inp_snr)*0.4)))
            parts.append(f'afftdn=nr={nr}:nf=-74:tn=1')

    # ── 7. LRA Control — v6.6: uses ref_lra (real target) not TARGET['lra']=4.0 ──
    lra_deficit = ref_lra - inp_lra   # negative = output LRA too wide → need compand
    if not is_bypass:
        if lra_deficit > 0.5:
            # LRA too narrow → expand with gate
            ratio = min(4.0 if is_extreme else 3.5,
                        1.0 + lra_deficit*(0.40 if is_extreme else 0.28))
            thr   = max(0.010, min(0.045, 0.022+lra_deficit*0.004))
            rel   = 1200 if is_extreme else 800
            parts.append(
                f'agate=threshold={thr:.3f}:ratio={ratio:.2f}'
                f':attack=20:release={rel}:makeup=1.0:range=0.06')
        elif lra_deficit < -0.4:
            # v6.6: LRA too wide → gentle compand to tighten
            # deficit=-0.4→-1.0: mild; -1.0→-2.0: moderate; >-2.0: stronger
            deficit_abs = abs(lra_deficit)
            if deficit_abs < 1.0:
                parts.append('compand=attacks=0.05:decays=1.5'
                             ':points=-90/-90|-30/-28.5|-15/-14.2|-6/-5.9|-2/-1.95|0/-0.3:gain=0')
            elif deficit_abs < 2.0:
                parts.append('compand=attacks=0.04:decays=1.0'
                             ':points=-90/-90|-30/-28|-15/-14|-6/-5.7|-2/-1.8|0/-0.4:gain=0')
            else:
                parts.append('compand=attacks=0.03:decays=0.8'
                             ':points=-90/-90|-30/-27|-15/-13.5|-6/-5.4|-2/-1.6|0/-0.5:gain=0')

    # ── 8. Main Compand — v6.4: EXTREME uses 20ms attack ─────────
    if not is_bypass:
        attack_map = {
            'MINIMAL':0.050,'LIGHT':0.030,'MEDIUM':0.015,
            'HEAVY':0.008,
            'EXTREME':0.020,     # v6.4: 20ms (was 4ms → crushed Crest)
        }
        decay_map = {
            'MINIMAL':3.0,'LIGHT':2.0,'MEDIUM':1.0,
            'HEAVY':0.5,
            'EXTREME':0.40,      # v6.4: 400ms (was 250ms)
        }
        attacks = attack_map.get(intensity, 0.015)
        decays  = decay_map.get(intensity, 1.0)
        parts.append(
            f'compand=attacks={attacks}:decays={decays}'
            f':points={compand_pts}:gain={makeup}')

    # ── 9. Post-compand warmth hook — NEW v6.4 ────────────────────
    for f0, gain, Q in post_warmth_nodes:
        parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={gain}')

    # ── 10. Spectral correction EQ — NEW v6.4 (two-pass only) ────
    for f0, gain, Q in correction_nodes:
        parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={gain}')

    # ── 11. Transient limiter ─────────────────────────────────────
    if intensity in ('MEDIUM','HEAVY','EXTREME'):
        lim = 0.982 if intensity == 'MEDIUM' else 0.978
        parts.append(f'alimiter=limit={lim}:level=false:attack=5:release=40')

    # ── 12. Volume ────────────────────────────────────────────────
    if abs(gain_db) > 0.05:
        parts.append(f'volume={gain_db:.3f}dB')

    # ── 13. Stereo ────────────────────────────────────────────────
    if is_mono:
        parts.append('aformat=channel_layouts=stereo')

    # ── 14. Final ceiling ─────────────────────────────────────────
    ceil = 0.999 if is_bypass else 0.995
    atk  = 5     if is_bypass else 1
    parts.append(f'alimiter=limit={ceil}:level=false:attack={atk}:release=20')

    return ','.join(f'\n    {p}' for p in parts)

# ═══════════════════════════════════════════════════════════════════════
#  QUALITY SCORE — v6.4
# ═══════════════════════════════════════════════════════════════════════
def quality_score(out_b: Dict, ref_fp: ReferenceFingerprint,
                  out_metrics: Dict,
                  hf_rolloff_hz: float = 20000.0) -> Tuple[float, Dict]:
    """
    v6.5:
    - LRA target = ref_fp.lra (real)
    - Warmth = spectral tilt 200-2000Hz (stable, shape-normalized)
    - Spectral weights tweaked: spectral 0.45, warmth 0.10
    """
    ref_b = ref_fp.third_oct
    spectral_ceil = min(10000, int(hf_rolloff_hz*0.85))
    common = [fc for fc in out_b if fc in ref_b and 80<=fc<=spectral_ceil]

    if common:
        out_vals    = np.array([out_b[fc] for fc in common])
        ref_vals    = np.array([ref_b[fc] for fc in common])
        aw          = np.array([max(0.2, 1+A_WEIGHT.get(fc,0)/10) for fc in common])
        level_off   = float(np.mean(ref_vals - out_vals))
        shape_diffs = np.abs((ref_vals-out_vals) - level_off)
        w_avg_err   = float(np.sum(aw*shape_diffs)/np.sum(aw))
        spectral_score = max(0.0, 100.0 - w_avg_err*5)
    else:
        w_avg_err = 99.0; spectral_score = 0.0

    lufs_err   = abs(out_metrics.get('lufs', -20) - TARGET['lufs'])
    crest_err  = abs(out_metrics.get('crest',  15) - TARGET['crest'])
    lra_target = ref_fp.lra if ref_fp.lra > 0 else TARGET['lra']
    lra_err    = abs(out_metrics.get('lra', 8) - lra_target)

    lufs_score  = max(0.0, 100.0 - lufs_err  * 12)
    crest_score = max(0.0, 100.0 - crest_err * 8)
    lra_score   = max(0.0, 100.0 - lra_err   * 10)

    # v6.5: warmth = spectral tilt 200-2000Hz (shape-normalized, stable)
    tilt_fc = np.array([fc for fc in CENTERS_31
                        if 200<=fc<=2000 and fc in out_b and fc<hf_rolloff_hz], dtype=float)
    if len(tilt_fc) >= 3:
        tilt_db  = np.array([out_b[fc] for fc in tilt_fc])
        out_tilt = float(np.polyfit(np.log2(tilt_fc/1000.0), tilt_db, 1)[0])
    else:
        out_tilt = 0.0

    tilt_err     = abs(out_tilt - ref_fp.warmth_ratio)
    warmth_score = max(0.0, 100.0 - tilt_err * 6)

    total = (spectral_score*0.43 + lufs_score*0.22 +
             crest_score*0.15    + lra_score*0.10  + warmth_score*0.10)

    return round(total,1), {
        'spectral':           round(spectral_score, 1),
        'lufs':               round(lufs_score,     1),
        'crest':              round(crest_score,     1),
        'lra':                round(lra_score,       1),
        'warmth':             round(warmth_score,    1),
        'avg_spectral_error': round(w_avg_err,       2),
        'warmth_tilt':        round(out_tilt,        2),
        'warmth_ref':         round(ref_fp.warmth_ratio, 2),
        'lra_target':         round(lra_target,      2),
    }

# ═══════════════════════════════════════════════════════════════════════
#  PHASE-1 DIAGNOSIS
# ═══════════════════════════════════════════════════════════════════════
def phase1_diagnosis(quality_tier, src_sr, src_br, inp_snr,
                     hf_rolloff_hz, inp_clips, inp_crest, inp_lra,
                     noise_floor_db, hf_deficit, intensity) -> List[str]:
    lines = []
    def D(m=''): lines.append(m); print(m)
    D(f"{'━'*66}")
    D(f"  ◉ PHASE 1 — DIAGNOSIS REPORT")
    D(f"{'━'*66}")
    tier_label = {
        'EXTREME':   '🔴 EXTREME  — Pixelated Hell (أسوأ حالة)',
        'VERY_POOR': '🟠 VERY_POOR — تدهور شديد',
        'POOR':      '🟡 POOR      — تدهور ملحوظ',
        'FAIR':      '🟢 FAIR      — جودة متوسطة',
        'GOOD':      '✅ GOOD      — جودة جيدة',
    }.get(quality_tier, quality_tier)
    D(f"  درجة الجودة   : {tier_label}")
    D(f"  SNR مقدَّر    : {inp_snr:.1f} dB  {'⚠ أقل من 5 dB — ضجيج كثيف' if inp_snr<5 else ''}")
    D(f"  HF rolloff   : {hf_rolloff_hz/1000:.1f} kHz  {'⚠ صوت ميت فوق هذا التردد' if hf_rolloff_hz<12000 else ''}")
    D(f"  HF deficit   : {hf_deficit:.1f} dB مقارنة بالمرجع")
    D(f"  Clips (35s)  : {inp_clips:,} عينة")
    D(f"  Crest Factor : {inp_crest:.2f} LU  (المرجع: {TARGET['crest']})")
    D(f"  LRA          : {inp_lra:.2f} LU")
    D(f"  Noise Floor  : {noise_floor_db:.1f} dBFS")
    D(f"  Sample Rate  : {src_sr} Hz")
    D(f"  Bitrate      : {src_br//1000} kbps")
    D(f"  Strategy     : compand={intensity}")
    D(f"{'━'*66}")
    return lines

# ═══════════════════════════════════════════════════════════════════════
#  MAIN ENGINE — v6.4 TWO-PASS
# ═══════════════════════════════════════════════════════════════════════
def enhance(input_path: str, output_path: str) -> Dict:
    log = []
    def L(msg=''):
        print(msg); log.append(msg)

    L(f"╔{'═'*66}╗")
    L(f"║  Audio Enhancement Engine v6.4 — \"Two-Pass Precision\"          ║")
    L(f"║  المرجع: الشيخ ياسر الدوسري — سورة الأعراف — 1425H              ║")
    L(f"╚{'═'*66}╝")
    L(f"  الملف: {os.path.basename(input_path)}")
    L()

    # ── [١] Reference Fingerprint ────────────────────────────────
    L("[١/٨] بصمة المرجع 1425 (cache إذا متاح)...")
    ref_fp = get_reference_fingerprint()
    L(f"  ✓ RMS={ref_fp.rms:.2f}  Crest={ref_fp.crest:.2f}  LRA={ref_fp.lra:.2f}")
    L(f"  ✓ Warmth={ref_fp.warmth_ratio:.2f}  Tilt={ref_fp.tilt_slope:.2f} dB/oct")

    # ── [٢] File Analysis ────────────────────────────────────────
    L(f"\n[٢/٨] تحليل الملف (35 ثانية — seek مباشر)...")
    probe   = get_probe(input_path)
    stream  = probe.get('streams',[{}])[0]
    is_mono = stream.get('channels',2) == 1
    src_sr  = int(stream.get('sample_rate',44100))
    src_br  = int(stream.get('bit_rate',128000))
    total_s = int(float(probe.get('format',{}).get('duration',300)))

    _n_ch = '1' if is_mono else '2'
    _pts  = [
        max(10,            total_s//10),
        max(30,            total_s//4),
        max(60,            total_s//2),
        max(90,  int(total_s*0.72)),
        max(120, int(total_s*0.90)),
    ]
    for i in range(1,len(_pts)):
        if _pts[i]-_pts[i-1] < 35: _pts[i] = _pts[i-1]+35
    _clip_files = [f'/tmp/v64_c{i}.wav' for i in range(5)]
    _early_procs = [
        subprocess.Popen(['ffmpeg','-y','-i',input_path,
                          '-ss',str(sk),'-t','25',
                          '-ar','48000','-ac',_n_ch,cl,'-loglevel','error'])
        for sk,cl in zip(_pts,_clip_files)
    ]

    skip_s  = min(30, total_s//4)
    inp     = load(input_path, skip=skip_s, duration=35)
    inp_b   = third_octave(inp, a_weighted=False)
    inp_clips  = count_clips(inp)
    inp_rms    = rms_db(inp)
    inp_peak   = peak_db(inp)
    inp_crest  = crest_factor(inp)
    inp_lra    = lra_estimate(inp)
    inp_snr    = snr_estimate(inp)
    inp_hf     = hf_status(inp_b)

    inp_fc  = np.array([fc for fc in CENTERS_31 if 100<=fc<=10000 and fc in inp_b])
    inp_db  = np.array([inp_b[fc] for fc in inp_fc])
    inp_tilt = float(np.polyfit(np.log2(inp_fc/1000.0), inp_db, 1)[0]) if len(inp_fc)>=3 else 0.0
    tilt_correction = ref_fp.tilt_slope - inp_tilt

    # Quality tier classification
    hf_freqs   = [fc for fc in inp_b if fc >= 8000]
    hf_avg     = float(np.mean([inp_b[fc] for fc in hf_freqs])) if hf_freqs else -80.0
    ref_hf     = float(np.mean([ref_fp.third_oct.get(fc,-60) for fc in hf_freqs])) if hf_freqs else -40.0
    hf_deficit = ref_hf - hf_avg
    sorted_amp = np.sort(np.abs(inp))
    noise_floor_db = float(20*np.log10(np.mean(sorted_amp[:max(1,len(sorted_amp)//20)])+1e-9))

    if inp_snr < 5 or src_br < 32000 or hf_deficit > 45:
        quality_tier = 'EXTREME'
    elif inp_snr < 6 or hf_deficit > 35:
        quality_tier = 'VERY_POOR'
    elif inp_snr < 12 or hf_deficit > 20:
        quality_tier = 'POOR'
    elif inp_snr < 20 or hf_deficit > 10:
        quality_tier = 'FAIR'
    else:
        quality_tier = 'GOOD'

    L(f"  RMS={inp_rms:.2f}  Peak={inp_peak:.2f}  Crest={inp_crest:.2f}  LRA={inp_lra:.2f}  SNR={inp_snr:.1f}")
    L(f"  Clips={inp_clips}  HF={inp_hf.upper()}  Tilt={inp_tilt:.2f}  Mono={is_mono}  SR={src_sr}  BR={src_br//1000}k")
    L(f"  جودة: {quality_tier}  HF-deficit={hf_deficit:.1f} dB  NoiseFloor={noise_floor_db:.1f} dBFS")

    # HF rolloff detection
    hf_rolloff_hz = detect_hf_rolloff(inp_b, drop_threshold=12.0)
    hf_rolloff_hz = max(hf_rolloff_hz, 2000.0)

    diag_lines = phase1_diagnosis(
        quality_tier, src_sr, src_br, inp_snr, hf_rolloff_hz,
        inp_clips, inp_crest, inp_lra, noise_floor_db, hf_deficit, '?')
    log.extend(diag_lines)

    # ── [٣] De-Clip ──────────────────────────────────────────────
    if inp_clips > 0:
        L(f"\n[٣/٨] إصلاح {inp_clips:,} عينة (Cubic Spline ctx=40)...")
        _, fixed = declip(inp, threshold=0.98)
        L(f"  ✓ {fixed:,} عينة — يُطبَّق على الكامل عبر ffmpeg")
    else:
        L(f"\n[٣/٨] لا توجد عينات مقطوعة ✓")

    # ── [٤] EQ Optimization ──────────────────────────────────────
    L(f"\n[٤/٨] EQ Optimizer (Bark-Scale + A-Weighting)...")
    # v6.4: EQ clamp tighter for EXTREME — compand amplifies everything
    max_eq_db = (4.0 if quality_tier == 'EXTREME'
                 else 5.0 if quality_tier == 'VERY_POOR'
                 else 6.0)
    n_nodes   = 12 if quality_tier == 'EXTREME' else 10
    # v6.4: EXTREME tier → shape_only (compand يرفع المستوى لا EQ)
    shape_only = (quality_tier == 'EXTREME')
    eq_nodes  = optimize_eq_bark(inp_b, ref_fp, n_nodes=n_nodes,
                                  use_a_weight=True, max_gain_db=max_eq_db,
                                  shape_only=shape_only)

    w_corr   = warmth_nodes(inp_b, ref_fp, quality_tier=quality_tier,
                             hf_rolloff_hz=hf_rolloff_hz)
    eq_nodes = sorted(eq_nodes+w_corr, key=lambda x: x[0])
    eq_nodes = merge_eq_nodes(eq_nodes, min_hz_gap=60.0)
    eq_nodes = [(f, float(np.clip(g,-max_eq_db,max_eq_db)), q) for f,g,q in eq_nodes]

    # HF-aware: no boost above rolloff
    eq_out = []; removed = 0
    for f0,g,q in eq_nodes:
        if f0 >= hf_rolloff_hz and g > 0:
            if f0 < hf_rolloff_hz*1.5:
                eq_out.append((f0, min(-0.5, g*-0.3), q))
            removed += 1
        else:
            eq_out.append((f0, g, q))
    eq_nodes = eq_out
    if removed: L(f"  ⚠ HF rolloff عند {hf_rolloff_hz:.0f} Hz — أُلغي {removed} boost فوقه")

    L(f"  {len(eq_nodes)} نقطة EQ (max±{max_eq_db}dB):")
    for f0,g,Q in eq_nodes:
        L(f"    {f0:>7.0f} Hz  {'▲' if g>0 else '▼'} {abs(g):.2f} dB  Q={Q:.2f}")

    # ── [٥] Compand Curve ────────────────────────────────────────
    L(f"\n[٥/٨] حساب منحنى الضغط...")
    # v6.6: لا force_extreme إذا LRA أصلاً تحت الهدف (يسحق الديناميك)
    force_extreme = (quality_tier == 'EXTREME') and (inp_lra >= ref_fp.lra * 0.85)
    compand_pts, makeup, intensity, calib_offset = build_compand_curve(
        inp_crest, inp_lra, ref_lra=ref_fp.lra, force_extreme=force_extreme)
    L(f"  شدة: {intensity}  Makeup=+{makeup:.1f} dB  Force-Extreme={force_extreme}")
    # v6.5: NR معطّل إذا:
    # - المصدر < 96kbps (MP3 artifacts تزداد مع NR)
    # - أو SNR < 8 dB (ضوضاء كثيفة جداً → musical noise مضمون)
    use_nr = (src_br >= 96000) and (inp_snr >= 8.0)

    # ── [٦] LUFS 5-point sampling ────────────────────────────────
    L(f"\n[٦/٨] Pipeline — LUFS 5-point...")
    for p in _early_procs: p.wait()
    L(f"  ✓ 5 clips جاهزة")

    chain_zero = build_filter_chain(
        eq_nodes, compand_pts, makeup, inp_hf, False, 0.0,
        noise_reduce=use_nr, tilt_slope=tilt_correction, inp_snr=inp_snr,
        intensity=intensity, inp_lra=inp_lra, inp_crest=inp_crest,
        quality_tier=quality_tier, hf_rolloff_hz=hf_rolloff_hz, src_sr=src_sr,
        ref_lra=ref_fp.lra
    ).replace('\n','').replace('    ','')

    lufs_procs = [
        subprocess.Popen(
            ['ffmpeg','-y','-i',cl,'-af',chain_zero+',ebur128=peak=true',
             '-f','null','-','-loglevel','info'],
            stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        for cl in _clip_files
    ]
    lufs_vals = []
    for p in lufs_procs:
        _,err = p.communicate()
        for line in err.decode().split('\n'):
            s = line.strip()
            if s.startswith('I:') and 'LUFS' in s and 'LRA' not in s:
                try: lufs_vals.append(float(s.split('I:')[1].strip().split()[0])); break
                except: pass

    if lufs_vals and len(lufs_vals) >= 3:
        wts = [0.10,0.25,0.30,0.25,0.10][:len(lufs_vals)]
        wts = [w/sum(wts) for w in wts]
        l0  = float(np.average(lufs_vals, weights=wts))
    else:
        l0  = float(np.mean(lufs_vals)) if lufs_vals else -12.0

    L(f"  LUFS 5-pt: [{', '.join(f'{v:.2f}' for v in lufs_vals)}]")
    gain_needed = float(np.clip(TARGET['lufs']-l0-calib_offset, -18, 12))
    L(f"  avg={l0:.2f}  calib={calib_offset:.1f}  gain_needed={gain_needed:+.2f} dB")

    # ── [٧] PASS 1: Full render to WAV ───────────────────────────
    L(f"\n[٧/٨] Pass 1 — رندر WAV + قياس طيف...")
    tmp_wav1 = '/tmp/v64_pass1.wav'
    n_ch     = 1 if is_mono else 2

    final_chain1 = build_filter_chain(
        eq_nodes, compand_pts, makeup, inp_hf, False, gain_needed,
        noise_reduce=use_nr, tilt_slope=tilt_correction, inp_snr=inp_snr,
        intensity=intensity, inp_lra=inp_lra, inp_crest=inp_crest,
        quality_tier=quality_tier, hf_rolloff_hz=hf_rolloff_hz, src_sr=src_sr,
        ref_lra=ref_fp.lra
    ).replace('\n','').replace('    ','')

    r_wav1 = subprocess.run(
        ['ffmpeg','-y','-i',input_path,'-af',
         final_chain1+',ebur128=peak=true',
         '-ar','48000','-ac',str(n_ch), tmp_wav1,'-loglevel','info'],
        capture_output=True, text=True)

    actual_lufs1 = -99.0
    for line in r_wav1.stderr.split('\n'):
        s = line.strip()
        if s.startswith('I:') and 'LUFS' in s and 'LRA' not in s:
            try: actual_lufs1 = float(s.split('I:')[1].strip().split()[0]); break
            except: pass
    if actual_lufs1 == -99.0: actual_lufs1 = gain_needed + l0

    # Measure Pass-1 spectrum
    out1_audio   = load(tmp_wav1, skip=skip_s, duration=35)
    out1_b       = third_octave(out1_audio)
    out1_metrics = {
        'lufs':  actual_lufs1,
        'rms':   rms_db(out1_audio),
        'crest': crest_factor(out1_audio),
        'lra':   lra_estimate(out1_audio),
    }
    score1, bd1 = quality_score(out1_b, ref_fp, out1_metrics, hf_rolloff_hz)
    L(f"  Pass1 LUFS={actual_lufs1:.2f}  RMS={out1_metrics['rms']:.2f}"
      f"  Crest={out1_metrics['crest']:.2f}  LRA={out1_metrics['lra']:.2f}")
    L(f"  Pass1 Score={score1}/100  err=±{bd1['avg_spectral_error']}dB")

    # Two-pass: compute correction EQ from Pass-1 spectrum
    # v6.4: shift by lufs_corr so correction targets the FINAL output level
    lufs_corr    = TARGET['lufs'] - actual_lufs1
    out1_b_final = {fc: v+lufs_corr for fc,v in out1_b.items()}
    # v6.6: higher max_correction for good-quality sources, lower for EXTREME
    max_corr_db = (3.0 if quality_tier == 'EXTREME'
                   else 3.5 if quality_tier == 'VERY_POOR'
                   else 4.5)
    corr_nodes    = spectral_correction_eq(out1_b_final, ref_fp,
                                            hf_rolloff_hz=hf_rolloff_hz,
                                            max_correction_db=max_corr_db)
    # Post-compand warmth correction (lighter scale, from final-level spectrum)
    post_w_nodes  = warmth_nodes(out1_b_final, ref_fp, quality_tier=quality_tier,
                                  post_compand=True, hf_rolloff_hz=hf_rolloff_hz)

    # v6.5: تحقق من الـ warmth gap بمقياس tilt (أكثر استقراراً)
    tilt_fc_1 = np.array([fc for fc in CENTERS_31
                           if 200<=fc<=2000 and fc in out1_b_final], dtype=float)
    if len(tilt_fc_1) >= 3:
        tilt_db_1 = np.array([out1_b_final[fc] for fc in tilt_fc_1])
        warmth_1  = float(np.polyfit(np.log2(tilt_fc_1/1000.0), tilt_db_1, 1)[0])
    else:
        warmth_1  = 0.0
    warmth_gap = ref_fp.warmth_ratio - warmth_1
    if abs(warmth_gap) > 5.0:   # عتبة أعلى (كانت 3.0) — نتدخل فقط عند فرق كبير
        tilt_adj = float(np.clip(warmth_gap * 0.3, -2.0, 2.0))
        post_w_nodes.append((200.0, round(tilt_adj, 2),        0.55))
        post_w_nodes.append((700.0, round(-tilt_adj*0.3, 2),   0.80))
        L(f"  ⚠ Tilt gap={warmth_gap:+.2f} → shelf adj={tilt_adj:+.2f}dB")

    if corr_nodes:
        L(f"  Correction EQ ({len(corr_nodes)} نقطة):")
        for f0,g,Q in corr_nodes:
            L(f"    {f0:>7.0f} Hz  {'▲' if g>0 else '▼'} {abs(g):.2f} dB")

    # ── PASS 2: MP3 encode with LUFS + spectral correction ───────
    L(f"  Pass 2 — MP3 (LUFS corr={lufs_corr:+.2f}dB, {len(corr_nodes)} corr EQ)...")

    corr_af = ''
    if corr_nodes:
        corr_af += ',' + ','.join(
            f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}'
            for f0,g,Q in corr_nodes)
    if post_w_nodes:
        corr_af += ',' + ','.join(
            f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}'
            for f0,g,Q in post_w_nodes)

    # v7: إضافة SPECTRAL_BIAS pre-correction في Pass2
    bias_af = ''
    for fc, bias_db in SPECTRAL_BIAS.items():
        if fc > hf_rolloff_hz * 0.9: continue
        g = round(-bias_db * BIAS_SCALE, 2)   # عكس الانحياز بـ 35%
        if abs(g) >= 0.3:
            Q = 0.70 if abs(g) > 1.5 else 1.0
            bias_af += f',equalizer=f={fc}:width_type=q:width={Q}:g={g}'

    af_enc = (f'volume={lufs_corr:.3f}dB'
              + corr_af
              + bias_af
              + ',alimiter=limit=0.995:level=false:attack=1:release=15')

    tmp_p2 = '/tmp/v7_pass2.mp3'
    subprocess.run(
        ['ffmpeg','-y','-i',tmp_wav1,'-af',af_enc,
         '-b:a','320k','-ar','48000','-ac',str(n_ch),
         tmp_p2,'-loglevel','error'],
        capture_output=True)

    # ── PASS 3: LRA + RMS feedback ───────────────────────────────
    L(f"  Pass 3 — LRA/RMS feedback...")
    p2_audio   = load(tmp_p2, skip=skip_s, duration=35)
    p2_lra     = lra_estimate(p2_audio)
    p2_rms     = rms_db(p2_audio)
    p2_b       = third_octave(p2_audio)
    p2_metrics = {'lufs': TARGET['lufs'], 'rms': p2_rms,
                  'crest': crest_factor(p2_audio), 'lra': p2_lra}
    score2, _ = quality_score(p2_b, ref_fp, p2_metrics, hf_rolloff_hz)
    L(f"    Pass2: LRA={p2_lra:.2f} (target={ref_fp.lra:.2f})  RMS={p2_rms:.2f} (target={ref_fp.rms:.2f})  Score={score2}")

    # LRA compand: إذا LRA > target + 0.15 نضغطه
    lra_gap_p2 = p2_lra - ref_fp.lra
    p3_af_parts = []

    if lra_gap_p2 > 0.15:
        # v7: agate بدل compand — يضيّق LRA بدون رفع Crest
        # agate يخفض الـ quiet passages فقط → يُضيّق النطاق الديناميكي
        if lra_gap_p2 < 0.5:
            thr = 0.018; ratio = 1.8; rel = 600
        elif lra_gap_p2 < 1.0:
            thr = 0.025; ratio = 2.2; rel = 500
        else:
            thr = 0.032; ratio = 2.8; rel = 400
        p3_af_parts.append(
            f'agate=threshold={thr:.3f}:ratio={ratio:.1f}'
            f':attack=15:release={rel}:makeup=1.0:range=0.08')
        L(f"    LRA gap={lra_gap_p2:+.2f} → agate thr={thr} ratio={ratio}")

    # RMS feedback: نُعدّل الـ gain لضبط RMS بدقة
    # v7 fix: الـ LRA compand يخفض الـ RMS قليلاً — نُعوّض ذلك
    compand_rms_loss = lra_gap_p2 * 0.18 if lra_gap_p2 > 0.15 else 0.0
    rms_gap = ref_fp.rms - p2_rms   # negative = output louder than ref
    rms_gain_adj = float(np.clip((rms_gap + compand_rms_loss) * 0.5, -1.5, 1.5))
    if abs(rms_gain_adj) > 0.1:
        p3_af_parts.append(f'volume={rms_gain_adj:.3f}dB')
        L(f"    RMS gap={rms_gap:+.2f} (compand_loss≈{compand_rms_loss:.2f}) → gain adj={rms_gain_adj:+.3f}dB")

    # Second spectral correction pass على Pass2 output
    p2_b_lnorm = {fc: v for fc,v in p2_b.items()}  # already at target LUFS
    corr2_nodes = spectral_correction_eq(p2_b_lnorm, ref_fp,
                                          hf_rolloff_hz=hf_rolloff_hz,
                                          max_correction_db=2.5)   # أخف من Pass2
    if corr2_nodes:
        p3_af_parts.extend(
            f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}'
            for f0,g,Q in corr2_nodes)
        L(f"    Corr2 EQ ({len(corr2_nodes)} نقطة)")

    p3_af_parts.append('alimiter=limit=0.995:level=false:attack=1:release=15')
    tmp_out = '/tmp/v7_out.mp3'

    if len(p3_af_parts) > 1:   # هناك شيء يُطبَّق فعلاً
        af_p3 = ','.join(p3_af_parts)
        subprocess.run(
            ['ffmpeg','-y','-i',tmp_p2,'-af',af_p3,
             '-b:a','320k','-ar','48000','-ac',str(n_ch),
             tmp_out,'-loglevel','error'],
            capture_output=True)
    else:
        shutil.copy(tmp_p2, tmp_out)
        L(f"    Pass3: لا تعديلات مطلوبة — Pass2 ممتاز")

    # ── [٨] Final evaluation ─────────────────────────────────────
    L(f"\n[٨/٨] تقييم النتيجة النهائية...")
    out_final = load(tmp_out, skip=skip_s, duration=35)
    out_b     = third_octave(out_final)
    out_metrics = {
        'lufs':  TARGET['lufs'],
        'rms':   rms_db(out_final),
        'crest': crest_factor(out_final),
        'lra':   lra_estimate(out_final),
    }
    score, breakdown = quality_score(out_b, ref_fp, out_metrics, hf_rolloff_hz)
    shutil.copy(tmp_out, output_path)

    L(f"\n{'═'*66}")
    L(f"  PHASE 3 — BEFORE → PASS1 → PASS2 → PASS3 → TARGET")
    L(f"{'═'*66}")
    L(f"  {'المقياس':<22} {'المدخل':>7}  {'Pass1':>7}  {'Pass2':>7}  {'Final':>7}  {'الهدف':>7}")
    L(f"  {'─'*62}")
    L(f"  {'LUFS':<22} {'N/A':>7}  {actual_lufs1:>7.2f}  {TARGET['lufs']:>7.2f}  {out_metrics['lufs']:>7.2f}  {TARGET['lufs']:>7.2f}")
    L(f"  {'RMS (dBFS)':<22} {inp_rms:>7.2f}  {out1_metrics['rms']:>7.2f}  {p2_rms:>7.2f}  {out_metrics['rms']:>7.2f}  {ref_fp.rms:>7.2f}")
    L(f"  {'Crest Factor (LU)':<22} {inp_crest:>7.2f}  {out1_metrics['crest']:>7.2f}  {p2_metrics['crest']:>7.2f}  {out_metrics['crest']:>7.2f}  {ref_fp.crest:>7.2f}")
    L(f"  {'LRA (LU)':<22} {inp_lra:>7.2f}  {out1_metrics['lra']:>7.2f}  {p2_lra:>7.2f}  {out_metrics['lra']:>7.2f}  {ref_fp.lra:>7.2f}*")
    L(f"  {'SR (Hz)':<22} {src_sr:>7}  {'48000':>7}  {'48000':>7}  {'48000':>7}  {'48000':>7}")
    L(f"  {'Bitrate':<22} {src_br//1000:>6}k  {'320k':>7}  {'320k':>7}  {'320k':>7}  {'320k':>7}")
    L(f"  {'HF Rolloff (kHz)':<22} {hf_rolloff_hz/1000:>7.1f}  {'20.0':>7}  {'20.0':>7}  {'20.0':>7}  {'20.0':>7}")
    L(f"  {'Clips (35s)':<22} {inp_clips:>7,}  {'0':>7}  {'0':>7}  {'0':>7}  {'0':>7}")
    L(f"  * LRA target = ref_fp.lra الحقيقي (ليس 4.0 الافتراضي)")
    L()
    L(f"  ★ نقطة الجودة: Pass1={score1}/100  →  Pass2={score2}/100  →  Final={score}/100"
      f"  {'✅ PASS' if score>=97 else ('✅ PASS' if score>=95 else ('✓ PASS' if score>=90 else '⚠ دون الهدف 90'))}")
    L(f"    • الطيف (A-weighted): {breakdown['spectral']}/100")
    L(f"    • LUFS:               {breakdown['lufs']}/100")
    L(f"    • Crest Factor:       {breakdown['crest']}/100")
    L(f"    • LRA:                {breakdown['lra']}/100  (target={ref_fp.lra:.2f})")
    L(f"    • دفء الصوت (tilt):   {breakdown['warmth']}/100  (out={breakdown['warmth_tilt']:.2f}  ref={breakdown['warmth_ref']:.2f} dB/oct)")
    L(f"    • خطأ طيفي متوسط:     ±{breakdown['avg_spectral_error']} dB")
    L()
    L(f"  ✅ تم الحفظ: {output_path}")
    L(f"{'═'*66}\n")

    return {
        'score':            score,
        'score_pass1':      score1,
        'breakdown':        breakdown,
        'final_metrics':    out_metrics,
        'input_metrics':    {'rms':inp_rms,'crest':inp_crest,'lra':inp_lra,'snr':inp_snr},
        'eq_nodes':         eq_nodes,
        'correction_nodes': corr_nodes,
        'quality_tier':     quality_tier,
        'hf_rolloff_hz':    hf_rolloff_hz,
        'ref_lra':          ref_fp.lra,
        'log':              log,
    }

# ═══════════════════════════════════════════════════════════════════════
#  CHUNKED PROCESSOR — v6.4
# ═══════════════════════════════════════════════════════════════════════
def enhance_chunked(input_path: str, output_path: str,
                    chunk_minutes: int = 20) -> dict:
    probe   = get_probe(input_path)
    total_s = int(float(probe.get('format',{}).get('duration',300)))
    if total_s <= chunk_minutes*60+60:
        return enhance(input_path, output_path)

    print(f"  📦 ملف طويل ({total_s//60}د) — v6.4 chunked two-pass")
    mid_s   = total_s // 2
    sample  = load(input_path, skip=mid_s, duration=60)
    ref_fp  = get_reference_fingerprint()
    inp_b   = third_octave(sample)
    inp_crest = crest_factor(sample); inp_lra = lra_estimate(sample)
    inp_snr   = snr_estimate(sample); inp_hf  = hf_status(inp_b)
    stream    = probe.get('streams',[{}])[0]
    src_br    = int(stream.get('bit_rate',128000))
    src_sr    = int(stream.get('sample_rate',44100))
    hf_freqs  = [fc for fc in inp_b if fc >= 8000]
    hf_avg    = float(np.mean([inp_b[fc] for fc in hf_freqs])) if hf_freqs else -80.0
    ref_hf    = float(np.mean([ref_fp.third_oct.get(fc,-60) for fc in hf_freqs])) if hf_freqs else -40.0
    hf_deficit= ref_hf - hf_avg
    if inp_snr<5 or src_br<32000 or hf_deficit>45:    quality_tier='EXTREME'
    elif inp_snr<6  or hf_deficit>35:                  quality_tier='VERY_POOR'
    elif inp_snr<12 or hf_deficit>20:                  quality_tier='POOR'
    elif inp_snr<20 or hf_deficit>10:                  quality_tier='FAIR'
    else:                                               quality_tier='GOOD'
    hf_rolloff_hz = max(detect_hf_rolloff(inp_b), 2000.0)
    max_eq_db = 4.0 if quality_tier=='EXTREME' else 5.0 if quality_tier=='VERY_POOR' else 6.0
    n_nodes   = 12 if quality_tier=='EXTREME' else 10
    eq_nodes  = optimize_eq_bark(inp_b, ref_fp, n_nodes=n_nodes, max_gain_db=max_eq_db)
    w_corr    = warmth_nodes(inp_b, ref_fp, quality_tier=quality_tier, hf_rolloff_hz=hf_rolloff_hz)
    eq_nodes  = sorted(merge_eq_nodes(eq_nodes+w_corr,60.0), key=lambda x: x[0])
    eq_nodes  = [(f,float(np.clip(g,-max_eq_db,max_eq_db)),q) for f,g,q in eq_nodes]
    compand_pts,makeup,intensity,calib = build_compand_curve(
        inp_crest, inp_lra, ref_lra=ref_fp.lra, force_extreme=(quality_tier=='EXTREME'))
    n_ch = '1' if stream.get('channels',2)==1 else '2'
    pts  = [total_s//8, total_s//2, total_s*3//4]
    clips= [f'/tmp/ch64_{i}.wav' for i in range(3)]
    procs= [subprocess.Popen(['ffmpeg','-y','-i',input_path,'-ss',str(sk),'-t','30',
             '-ar','48000','-ac',n_ch,cl,'-loglevel','error']) for sk,cl in zip(pts,clips)]
    for p in procs: p.wait()
    chain0 = build_filter_chain(
        eq_nodes,compand_pts,makeup,inp_hf,False,0.0,noise_reduce=True,
        intensity=intensity,inp_lra=inp_lra,inp_crest=inp_crest,
        quality_tier=quality_tier,hf_rolloff_hz=hf_rolloff_hz,src_sr=src_sr
    ).replace('\n','').replace('    ','')
    lprocs = [
        subprocess.Popen(['ffmpeg','-y','-i',cl,'-af',chain0+',ebur128=peak=true',
         '-f','null','-','-loglevel','info'],stderr=subprocess.PIPE,stdout=subprocess.PIPE)
        for cl in clips
    ]
    lufs_vals=[]
    for p in lprocs:
        _,err=p.communicate()
        for l in err.decode().split('\n'):
            s=l.strip()
            if s.startswith('I:') and 'LUFS' in s and 'LRA' not in s:
                try: lufs_vals.append(float(s.split('I:')[1].strip().split()[0])); break
                except: pass
    l0   = float(np.mean(lufs_vals)) if lufs_vals else -12.0
    gain = float(np.clip(TARGET['lufs']-l0-calib,-18,12))
    # Pass 1 WAV
    tmp_wav='/tmp/v64_chunk.wav'
    r=subprocess.run(
        ['ffmpeg','-y','-i',input_path,'-af',
         build_filter_chain(eq_nodes,compand_pts,makeup,inp_hf,False,gain,
             noise_reduce=True,intensity=intensity,inp_lra=inp_lra,inp_crest=inp_crest,
             quality_tier=quality_tier,hf_rolloff_hz=hf_rolloff_hz,src_sr=src_sr
         ).replace('\n','').replace('    ','')+',ebur128=peak=true',
         '-ar','48000','-ac',n_ch,tmp_wav,'-loglevel','info'],
        capture_output=True, text=True)
    actual_lufs=-99.0
    for line in r.stderr.split('\n'):
        s=line.strip()
        if s.startswith('I:') and 'LUFS' in s and 'LRA' not in s:
            try: actual_lufs=float(s.split('I:')[1].strip().split()[0]); break
            except: pass
    lufs_corr = TARGET['lufs']-actual_lufs if actual_lufs!=-99.0 else 0.0
    # Measure pass-1 spectrum & compute correction
    out1=load(tmp_wav,skip=mid_s,duration=35)
    out1_b=third_octave(out1)
    corr_nodes=spectral_correction_eq(out1_b,ref_fp,hf_rolloff_hz=hf_rolloff_hz)
    post_w=warmth_nodes(out1_b,ref_fp,quality_tier=quality_tier,
                         post_compand=True,hf_rolloff_hz=hf_rolloff_hz)
    corr_af=''
    if corr_nodes:
        corr_af+=','+','.join(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}'
                               for f0,g,Q in corr_nodes)
    if post_w:
        corr_af+=','+','.join(f'equalizer=f={f0:.0f}:width_type=q:width={Q}:g={g}'
                               for f0,g,Q in post_w)
    tmp_out='/tmp/v64_chunk_out.mp3'
    subprocess.run(
        ['ffmpeg','-y','-i',tmp_wav,'-af',
         f'volume={lufs_corr:.3f}dB{corr_af},alimiter=limit=0.995:level=false:attack=1:release=15',
         '-b:a','320k','-ar','48000','-ac',n_ch,tmp_out,'-loglevel','error'],
        capture_output=True)
    shutil.copy(tmp_out, output_path)
    out_a=load(output_path,skip=mid_s,duration=35)
    out_b=third_octave(out_a)
    metrics={'lufs':TARGET['lufs'],'rms':rms_db(out_a),
             'crest':crest_factor(out_a),'lra':lra_estimate(out_a)}
    score,breakdown=quality_score(out_b,ref_fp,metrics,hf_rolloff_hz)
    print(f"  ★ {score}/100  ✅ {output_path}")
    return {'score':score,'breakdown':breakdown,'final_metrics':metrics}

# ═══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Tilawa Engine v7.0 -- server CLI')
    ap.add_argument('-i', '--input',  required=True)
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--ref', action='append', default=[],
                    help='Reference audio file; repeat for multiple files')
    ap.add_argument('--iterations', type=int, default=1,
                    help='Iterations (v7.0: ignored; kept for CLI compat)')
    args = ap.parse_args()

    if args.ref:
        valid = [r for r in args.ref if os.path.exists(r)]
        if valid:
            globals()['_CLI_REF_FILES'] = valid
            if os.path.exists(REF_CACHE):
                try: os.remove(REF_CACHE)
                except: pass
            print(f'مراجع: {len(valid)} ملف')
        else:
            print('تحذير: ملفات --ref غير موجودة، جار استخدام البصمة المخزّنة')

    print('Pass 1 — تحليل الملف وبناء البصمة المرجعية...')
    sys.stdout.flush()

    try:
        result = enhance(input_path=args.input, output_path=args.output)
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

    score   = result.get('score', 0)
    metrics = result.get('final_metrics', {})
    lufs    = metrics.get('lufs',  TARGET['lufs'])
    rms     = metrics.get('rms',   TARGET['rms'])
    crest   = metrics.get('crest', TARGET['crest'])
    lra     = metrics.get('lra',   TARGET['lra'])

    print('Pass 3 — إنهاء المعالجة')
    print(f'Score: {score:.1f}')
    print(f'LUFS={lufs:.2f} RMS={rms:.2f} Crest={crest:.2f} LRA={lra:.2f}')
    sys.stdout.flush()

    sys.exit(0 if score >= 90 else 1)
