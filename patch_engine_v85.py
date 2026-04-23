#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_engine_v85.py
engine_v845.py → engine_v85.py

v8.5 — TIER-ADJUSTED SCORING (TierAdjustedScoring)
====================================================
v8.4 built a SourceTierDetector that correctly detects source quality tier
and routes processing accordingly.  v8.45 extracted deep reference model
fields (phrase LRA distribution, silence floor, codec cutoff).

v8.5 answers the question the scoring system never asked:

  "A 64kbps file that reaches its physical ceiling — should it score 75/100
   because it cannot hit 10.25LU Crest, or 95/100 because it hit everything
   it was physically capable of?"

The answer is 95/100.  The current scorer penalises the engine for limits
imposed by the SOURCE, not by the processing.  That produces wrong compand
decisions and misleads the user.

DESIGN DECISIONS (v8.5)
──────────────────────
• score_absolute: always scored vs the original 1425H targets.
  Never changes.  This is the "ground truth" distance from ideal.

• score_tier: scored vs achievable targets for this source tier.
  This is what is DISPLAYED to the user and used for convergence decisions.
  A TIER_COMPRESSED source has Crest ceiling 9.8LU, so a result of 9.75LU
  scores Crest as ~100 rather than ~79.

• ceiling_reason: logged string explaining the adjusted ceiling so the user
  understands why the tier score is higher than the absolute score.

• compute_mds() gains source_tier parameter → tier-specific MDS weights.
  TIER_DAMAGED sources: SNR/SFM matter most (40%/30%).  HF is irrelevant (0%).
  TIER_PRISTINE: balanced weights as before.
  Recomputed AFTER tier detection, before compand — heavier processing on
  truly damaged sources that previously under-scored on SNR.

• 64K_FLOOR ad-hoc hack removed.  Replaced by the systematic tier logic.

PATCHES IN THIS FILE
────────────────────
  P1a  Version string → v8.5
  P1b  Cache → ref_fp.v85.json
  P1c  Log string for cache
  P2   QualityReport — 3 new fields (score_absolute, score_tier, ceiling_reason)
  P3   Insert TierAdjustedScoring module (_V85_MDS_WEIGHTS + _compute_achievable_targets)
  P4a  compute_mds() signature — add source_tier param
  P4b  compute_mds() weighted sum — use _V85_MDS_WEIGHTS
  P5a  quality_score() section header comment
  P5b  quality_score() signature — add source_tier + input_cutoff_hz
  P5c  quality_score() body — replace lufs/crest/lra block + 64K_FLOOR → tier logic
  P6   enhance() — recompute MDS with tier after SourceTierDetector, update damage
  P7a  quality_score(p1_b,...) call → pass tier
  P7b  quality_score(p2_b,...) call → pass tier
  P7c  quality_score(p3_b,...) call → pass tier
  P7d  quality_score(out_b_,...) call → pass tier
  P7e  quality_score(fin_b,...) call → pass tier
  P8   FINAL REPORT score bar → add v8.5 tier/absolute lines + ceiling_reason
  P9   FINAL REPORT — add [v8.5] summary block after [v8.45] block
  P10  FINAL REPORT header line v8.4 → v8.5
  P11  Return dict — engine_version + score_absolute + score_tier + ceiling_reason
  P12  app.py — register engine_v85.py, update default
"""

import sys
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
REPO       = Path.home() / 'tilawa-enhancer'
SRC_ENGINE = REPO / 'engine_v845.py'
DST_ENGINE = REPO / 'engine_v85.py'
APP_PY     = REPO / 'app.py'

assert SRC_ENGINE.exists(), f"ABORT: {SRC_ENGINE} not found"
assert APP_PY.exists(),     f"ABORT: {APP_PY} not found"

src    = SRC_ENGINE.read_text(encoding='utf-8')
errors = []


def check(cond, label):
    if not cond:
        errors.append(label)
        print(f"FAIL: {label}")
    else:
        print(f"OK:   {label}")


def replace1(old, new, label):
    global src
    check(old in src, label)
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════════
# P1 — Version string + cache filename
# ══════════════════════════════════════════════════════════════════════════════
replace1(
    "description='Audio Enhancement Engine v8.45 \u2014 1425H'",
    "description='Audio Enhancement Engine v8.5 \u2014 1425H'",
    "P1a version string"
)
replace1(
    "REF_CACHE   = str(_CACHE_DIR / 'ref_fp.v845.json')  # v8.45: cache version bump",
    "REF_CACHE   = str(_CACHE_DIR / 'ref_fp.v85.json')   # v8.5: cache version bump",
    "P1b cache filename"
)
replace1(
    "    \u2713 REF_CACHE \u2192 ~/.tilawa_cache/ref_fp.v845.json (v8.45 version bump)",
    "    \u2713 REF_CACHE \u2192 ~/.tilawa_cache/ref_fp.v85.json (v8.5 version bump)",
    "P1c log cache string"
)

# ══════════════════════════════════════════════════════════════════════════════
# P2 — QualityReport: add score_absolute, score_tier, ceiling_reason
# ══════════════════════════════════════════════════════════════════════════════
OLD_P2 = "    notes:       List[str] = field(default_factory=list)"
NEW_P2 = """\
    notes:       List[str] = field(default_factory=list)
    # ── v8.5: TierAdjustedScoring fields ─────────────────────────────────────
    score_absolute: float = 0.0   # scored vs original 1425H targets (always)
    score_tier:     float = 0.0   # scored vs tier-achievable targets (displayed)
    ceiling_reason: str   = ''    # e.g. "TIER_COMPRESSED: Crest\u22649.8LU  LRA\u22644.0LU"""
replace1(OLD_P2, NEW_P2, "P2 QualityReport new fields")

# ══════════════════════════════════════════════════════════════════════════════
# P3 — Insert TierAdjustedScoring module before compute_mds()
# ══════════════════════════════════════════════════════════════════════════════
P3_ANCHOR = "def compute_mds(snr:float,sfm:float,dr:float,hf_deficit:float,"
P3_INSERT = '''\
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  v8.5 \u2014 TIER-ADJUSTED SCORING (TierAdjustedScoring)
#  Per-tier MDS weights for compute_mds() and achievable target dicts
#  for quality_score().  Replaces the ad-hoc 64K_FLOOR hack.
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

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
        # Linear: 7.5LU at cutoff=0Hz \u2192 9.0LU at cutoff=10500Hz
        crest_ceil = float(np.clip(7.5 + (input_cutoff_hz / 10500.0) * 1.5, 7.5, 9.0))
        return {**TARGET, 'crest': crest_ceil, 'lra': 3.6, 'lufs': -6.5}
    # TIER_DAMAGED
    return {**TARGET, 'crest': 7.0, 'lra': 3.2, 'lufs': -7.0}


'''
replace1(P3_ANCHOR, P3_INSERT + P3_ANCHOR, "P3 TierAdjustedScoring module")

# ══════════════════════════════════════════════════════════════════════════════
# P4a — compute_mds() signature: add source_tier parameter
# ══════════════════════════════════════════════════════════════════════════════
OLD_P4A = """\
def compute_mds(snr:float,sfm:float,dr:float,hf_deficit:float,
                spectral_dist:float,src_br:int,
                ref_sfm:float=TARGET['sfm'],
                ref_dr:float=TARGET['dr']) -> float:"""
NEW_P4A = """\
def compute_mds(snr:float,sfm:float,dr:float,hf_deficit:float,
                spectral_dist:float,src_br:int,
                ref_sfm:float=TARGET['sfm'],
                ref_dr:float=TARGET['dr'],
                source_tier:str='TIER_PRISTINE') -> float:"""
replace1(OLD_P4A, NEW_P4A, "P4a compute_mds signature")

# ══════════════════════════════════════════════════════════════════════════════
# P4b — compute_mds() weighted sum: use _V85_MDS_WEIGHTS
# ══════════════════════════════════════════════════════════════════════════════
OLD_P4B = """\
    mds=(snr_score*0.25+sfm_score*0.25+spec_score*0.20+
         hf_score*0.15+dr_score*0.10+br_score*0.05)
    return float(np.clip(mds,0,100))"""
NEW_P4B = """\
    # v8.5: tier-specific weights — TIER_DAMAGED weights SNR/SFM heavily, HF=0
    w = _V85_MDS_WEIGHTS.get(source_tier, _V85_MDS_WEIGHTS['TIER_PRISTINE'])
    mds = (snr_score * w['snr'] + sfm_score * w['sfm'] + spec_score * w['spec'] +
           hf_score  * w['hf']  + dr_score  * w['dr']  + br_score   * w['br'])
    return float(np.clip(mds, 0, 100))"""
replace1(OLD_P4B, NEW_P4B, "P4b compute_mds weighted sum")

# ══════════════════════════════════════════════════════════════════════════════
# P5a — quality_score() section header comment
# ══════════════════════════════════════════════════════════════════════════════
OLD_P5A = """\
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  QUALITY SCORE (\u0645\u062d\u0627\u0641\u064e\u0638 \u0639\u0644\u064a\u0647 \u2014 ref_fp.lra = 4.19 \u0635\u062d\u064a\u062d \u0645\u0646\u0630 v7.6)
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"""
NEW_P5A = """\
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  QUALITY SCORE \u2014 v8.5 TIER-ADJUSTED SCORING
#  score_tier:     vs achievable targets for source tier (displayed to user)
#  score_absolute: vs original 1425H targets always (honest reference)
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"""
replace1(OLD_P5A, NEW_P5A, "P5a quality_score section header")

# ══════════════════════════════════════════════════════════════════════════════
# P5b — quality_score() signature: add source_tier + input_cutoff_hz
# ══════════════════════════════════════════════════════════════════════════════
OLD_P5B = """\
def quality_score(out_b:Dict,ref_fp:ReferenceFingerprint,
                  metrics:Dict,hf_rolloff:float=20000.0) -> Tuple[float,QualityReport]:"""
NEW_P5B = """\
def quality_score(out_b:Dict,ref_fp:ReferenceFingerprint,
                  metrics:Dict,hf_rolloff:float=20000.0,
                  source_tier:str='TIER_PRISTINE',
                  input_cutoff_hz:float=20000.0) -> Tuple[float,QualityReport]:"""
replace1(OLD_P5B, NEW_P5B, "P5b quality_score signature")

# ══════════════════════════════════════════════════════════════════════════════
# P5c — quality_score() body: replace metric block + 64K_FLOOR hack
#       The anchor starts at "lufs_e=..." and ends at "return rpt.score,rpt"
# ══════════════════════════════════════════════════════════════════════════════
OLD_P5C = """\
    lufs_e=abs(metrics.get('lufs',-20)-TARGET['lufs'])
    crest_e=abs(metrics.get('crest',15)-TARGET['crest'])
    lra_t=ref_fp.lra  # 4.19 \u2014 \u0635\u062d\u064a\u062d \u0641\u064a v7.6 \u0648v8
    lra_e=abs(metrics.get('lra',8)-lra_t)
    lufs_s=max(0.0,100.0-lufs_e*12)
    crest_s=max(0.0,100.0-crest_e*8)
    lra_s=max(0.0,100.0-lra_e*10)

    tfc=np.array([fc for fc in CENTERS_31 if 200<=fc<=2000
                   and fc in out_b and fc<hf_rolloff],dtype=float)
    out_tilt=(float(np.polyfit(np.log2(tfc/1000.0),
                               np.array([out_b[fc] for fc in tfc]),1)[0])
              if len(tfc)>=3 else 0.0)
    warmth_s=max(0.0,100.0-abs(out_tilt-ref_fp.warmth_ratio)*5.5)

    hf_fcs=[fc for fc in [4000,5000,6300,8000,10000,12500]
            if fc<hf_rolloff and fc in out_b and fc in ref_b]
    if len(hf_fcs)>=3:
        hf_o=np.array([out_b[fc] for fc in hf_fcs])
        hf_r=np.array([ref_b[fc] for fc in hf_fcs])
        hf_e=float(np.mean(np.abs((hf_r-hf_o)-float(np.mean(hf_r-hf_o)))))
        hf_s=max(0.0,100.0-hf_e*4)
    else: hf_s=50.0

    total=(spectral_s*0.38+lufs_s*0.20+crest_s*0.15+
           lra_s*0.12+warmth_s*0.10+hf_s*0.05)

    notes=[]
    if lufs_e>0.6:  notes.append(f"LUFS:{metrics.get('lufs',-99):.2f}\u2192{TARGET['lufs']}")
    if crest_e>1.2: notes.append(f"Crest:{metrics.get('crest',0):.2f}\u2192{TARGET['crest']}")
    if lra_e>1.0:   notes.append(f"LRA:{metrics.get('lra',0):.2f}\u2192{lra_t:.2f}")
    if w_avg>2.5:   notes.append(f"Spectral:\xb1{w_avg:.2f}dB")

    rpt=QualityReport(
        score=round(total,1),spectral=round(spectral_s,1),
        lufs=round(lufs_s,1),crest=round(crest_s,1),lra=round(lra_s,1),
        warmth=round(warmth_s,1),hf=round(hf_s,1),
        avg_err=round(w_avg,2),warmth_tilt=round(out_tilt,2),
        warmth_ref=round(ref_fp.warmth_ratio,2),lra_target=round(lra_t,2),
        notes=notes)

    # v8.1 PATCH #5: 64K_FLOOR \u2014 document source-limited Crest ceiling
    # A 64kbps encoder crushes transient peaks; Crest \u22489.5LU is the physical ceiling.
    # This is NOT a processing failure \u2014 score accordingly.
    src_br_val = metrics.get('src_br', 320000)
    final_crest_val = metrics.get('crest', TARGET['crest'])
    if src_br_val < 80000 and final_crest_val < 10.0:
        floor_note = (
            f'64K_FLOOR: Crest {final_crest_val:.2f}LU \u2014 '
            f'source codec ceiling ~9.5LU, '
            f'target {TARGET["crest"]}LU unachievable from '
            f'{src_br_val//1000}kbps source (not a processing error)'
        )
        rpt.notes.insert(0, floor_note)
        # Adjust Crest score: penalise against realistic 64kbps ceiling (9.8LU)
        # instead of the ideal target, to fairly represent processing quality.
        achievable_crest = 9.8
        crest_s_adj = max(0.0, 100.0 - abs(achievable_crest - TARGET['crest']) * 8)
        total_adj = (spectral_s*0.38 + lufs_s*0.20 + crest_s_adj*0.15 +
                     lra_s*0.12 + warmth_s*0.10 + hf_s*0.05)
        rpt.score = round(total_adj, 1)

    return rpt.score,rpt"""

NEW_P5C = """\
    lra_t = ref_fp.lra  # 4.19 (\u0635\u062d\u064a\u062d \u0645\u0646\u0630 v7.6)

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

    # ── score_absolute: vs original 1425H targets \u2014 never changes ─────────────────
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

    # ── ceiling_reason \u2014 logged when tier relaxes targets ──────────────────────
    ceiling_reason = ''
    if source_tier != 'TIER_PRISTINE':
        ceiling_reason = (
            f"{source_tier}: Crest\u2264{at['crest']:.2f}LU  "
            f"LRA\u2264{at['lra']:.2f}LU  LUFS\u2265{at['lufs']:.2f}  "
            f"[cutoff={input_cutoff_hz:.0f}Hz]"
        )

    notes = []
    if abs(lufs_val - TARGET['lufs']) > 0.6:
        notes.append(f"LUFS:{lufs_val:.2f}\u2192{TARGET['lufs']}")
    if abs(crest_val - at['crest']) > 1.2:
        notes.append(f"Crest:{crest_val:.2f}\u2192{at['crest']:.2f}")
    if abs(lra_val - at['lra']) > 1.0:
        notes.append(f"LRA:{lra_val:.2f}\u2192{at['lra']:.2f}")
    if w_avg > 2.5:
        notes.append(f"Spectral:\xb1{w_avg:.2f}dB")

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
    return rpt.score, rpt"""

replace1(OLD_P5C, NEW_P5C, "P5c quality_score body + 64K_FLOOR removal")

# ══════════════════════════════════════════════════════════════════════════════
# P6 — enhance(): recompute MDS with tier after SourceTierDetector
#      Insert after the ✦ Ceiling log line, before STEP 2
# ══════════════════════════════════════════════════════════════════════════════
OLD_P6 = "    use_nr = tier_profile.nr_mandatory or ((src_br >= 96000) and (snr_global >= 8.0))"
NEW_P6 = """\
    # v8.5: recompute MDS with tier-specific weights now that tier is known.
    # TIER_DAMAGED weights SNR/SFM heavily (40%/30%), ignores HF (0%).
    # This raises MDS for truly damaged sources -> heavier compand (correct).
    mds = compute_mds(snr_global, inp_sfm, inp_dr, hf_deficit, spec_dist, src_br,
                      ref_fp.sfm, ref_fp.dr, source_tier=tier_profile.tier)
    quality_label = mds_to_label(mds)
    damage.mds = mds
    damage.quality_label = quality_label
    L(f"  [v8.5] MDS (tier-adjusted) = {mds:.1f}/100 -> {quality_label}"
      f"  [{tier_profile.tier} weights]")

    use_nr = tier_profile.nr_mandatory or ((src_br >= 96000) and (snr_global >= 8.0))"""
replace1(OLD_P6, NEW_P6, "P6 enhance() recompute MDS after tier")

# ══════════════════════════════════════════════════════════════════════════════
# P7a–e — quality_score() call sites: pass tier + cutoff
# ══════════════════════════════════════════════════════════════════════════════
replace1(
    "        s1,_=quality_score(p1_b,ref_fp,p1_m,hf_rolloff)",
    "        s1,_=quality_score(p1_b,ref_fp,p1_m,hf_rolloff,"
    "\n                            tier_profile.tier,tier_profile.input_cutoff_hz)",
    "P7a s1 quality_score call"
)
replace1(
    "        s2,_=quality_score(p2_b,ref_fp,p2_m,hf_rolloff)",
    "        s2,_=quality_score(p2_b,ref_fp,p2_m,hf_rolloff,"
    "\n                            tier_profile.tier,tier_profile.input_cutoff_hz)",
    "P7b s2 quality_score call"
)
replace1(
    "        s3,_=quality_score(p3_b,ref_fp,p3_m,hf_rolloff)",
    "        s3,_=quality_score(p3_b,ref_fp,p3_m,hf_rolloff,"
    "\n                            tier_profile.tier,tier_profile.input_cutoff_hz)",
    "P7c s3 quality_score call"
)
replace1(
    "        fs,fbd=quality_score(out_b_,ref_fp,out_m,hf_rolloff)",
    "        fs,fbd=quality_score(out_b_,ref_fp,out_m,hf_rolloff,"
    "\n                              tier_profile.tier,tier_profile.input_cutoff_hz)",
    "P7d fs quality_score call"
)
replace1(
    "    top_s,top_bd=quality_score(fin_b,ref_fp,fin_m,hf_rolloff)",
    "    top_s,top_bd=quality_score(fin_b,ref_fp,fin_m,hf_rolloff,"
    "\n                               tier_profile.tier,tier_profile.input_cutoff_hz)",
    "P7e top_s quality_score call"
)

# ══════════════════════════════════════════════════════════════════════════════
# P8 — FINAL REPORT score bar: add tier/absolute breakdown after the ★ line
# ══════════════════════════════════════════════════════════════════════════════
OLD_P8 = """\
    bar='\u2588'*int(top_s/5)+'\u2591'*(20-int(top_s/5))
    L()
    L(f"  \u2605 {bar} {top_s}/100"
      f"  {'\u2705 EXCELLENT' if top_s>=96 else '\u2705 PASS' if top_s>=92 else '\u2713' if top_s>=88 else '\u26a0'}")
    L(f"    Spectral:{top_bd.spectral} LUFS:{top_bd.lufs} Crest:{top_bd.crest}"
      f" LRA:{top_bd.lra} Warmth:{top_bd.warmth} HF:{top_bd.hf}")"""
NEW_P8 = """\
    bar='\u2588'*int(top_s/5)+'\u2591'*(20-int(top_s/5))
    L()
    L(f"  \u2605 {bar} {top_s}/100"
      f"  {'\u2705 EXCELLENT' if top_s>=96 else '\u2705 PASS' if top_s>=92 else '\u2713' if top_s>=88 else '\u26a0'}")
    # v8.5: show both tier-adjusted and absolute scores
    if top_bd.ceiling_reason:
        L(f"    [v8.5] score_tier={top_bd.score_tier}/100"
          f"  score_absolute={top_bd.score_absolute}/100"
          f"  (ceiling adjusted for {tier_profile.tier})")
        L(f"    \u24d8 {top_bd.ceiling_reason}")
    else:
        L(f"    [v8.5] score_tier={top_bd.score_tier}/100"
          f"  score_absolute={top_bd.score_absolute}/100  (TIER_PRISTINE \u2014 no adjustment)")
    L(f"    Spectral:{top_bd.spectral} LUFS:{top_bd.lufs} Crest:{top_bd.crest}"
      f" LRA:{top_bd.lra} Warmth:{top_bd.warmth} HF:{top_bd.hf}")"""
replace1(OLD_P8, NEW_P8, "P8 FINAL REPORT score bar v8.5 lines")

# ══════════════════════════════════════════════════════════════════════════════
# P9 — FINAL REPORT: add [v8.5] summary block after [v8.45] block
# ══════════════════════════════════════════════════════════════════════════════
OLD_P9 = """\
    lra_p3_used = ref_fp.phrase_lra_p50 if ref_fp.phrase_lra_p50 > 0.1 else ref_fp.lra
    L(f"  [v8.45] REF MODEL  "
      f"n_refs={ref_fp.n_files}  "
      f"p50_lra={ref_fp.phrase_lra_p50:.2f}LU  "
      f"peak={ref_fp.peak_distribution}  "
      f"sil={ref_fp.silence_floor_db:.1f}dBFS  "
      f"cutoff={ref_fp.ref_codec_cutoff_hz:.0f}Hz")
    L(); L(f"  \u2705 {output_path}"); L(f"{'═'*70}\\n")"""
NEW_P9 = """\
    lra_p3_used = ref_fp.phrase_lra_p50 if ref_fp.phrase_lra_p50 > 0.1 else ref_fp.lra
    L(f"  [v8.45] REF MODEL  "
      f"n_refs={ref_fp.n_files}  "
      f"p50_lra={ref_fp.phrase_lra_p50:.2f}LU  "
      f"peak={ref_fp.peak_distribution}  "
      f"sil={ref_fp.silence_floor_db:.1f}dBFS  "
      f"cutoff={ref_fp.ref_codec_cutoff_hz:.0f}Hz")
    L(f"  v8.5 Tier-Adjusted Scoring:")
    L(f"    \u2713 score_tier={top_bd.score_tier}/100  score_absolute={top_bd.score_absolute}/100")
    L(f"    \u2713 compute_mds tier-weighted: {tier_profile.tier} "
      f"(SNR w={_V85_MDS_WEIGHTS[tier_profile.tier]['snr']:.2f}"
      f" SFM w={_V85_MDS_WEIGHTS[tier_profile.tier]['sfm']:.2f}"
      f" HF w={_V85_MDS_WEIGHTS[tier_profile.tier]['hf']:.2f})")
    L(f"    \u2713 64K_FLOOR hack removed \u2014 replaced by TierAdjustedScoring")
    if top_bd.ceiling_reason:
        L(f"    \u2713 ceiling: {top_bd.ceiling_reason}")
    L(f"  [v8.5] TIER-SCORE  "
      f"tier={tier_profile.tier}  "
      f"score_tier={top_bd.score_tier}/100  "
      f"score_abs={top_bd.score_absolute}/100  "
      f"MDS={mds:.1f}")
    L(); L(f"  \u2705 {output_path}"); L(f"{'═'*70}\\n")"""
replace1(OLD_P9, NEW_P9, "P9 FINAL REPORT v8.5 summary block")

# ══════════════════════════════════════════════════════════════════════════════
# P10 — FINAL REPORT header line: v8.4 → v8.5
# ══════════════════════════════════════════════════════════════════════════════
replace1(
    'L(f"  FINAL REPORT \u2014 v8.4 ({elapsed:.0f}s)")',
    'L(f"  FINAL REPORT \u2014 v8.5 ({elapsed:.0f}s)")',
    "P10 FINAL REPORT version line"
)

# ══════════════════════════════════════════════════════════════════════════════
# P11 — Return dict: engine_version + score fields
# ══════════════════════════════════════════════════════════════════════════════
replace1(
    "'engine_version':'v8.45',",
    ("'engine_version':'v8.5',\n"
     "        'score_absolute':top_bd.score_absolute,\n"
     "        'score_tier':top_bd.score_tier,\n"
     "        'ceiling_reason':top_bd.ceiling_reason,"),
    "P11 return dict engine_version + score fields"
)

# ══════════════════════════════════════════════════════════════════════════════
# Write engine_v85.py
# ══════════════════════════════════════════════════════════════════════════════
if errors:
    print(f"\n{'='*60}")
    print(f"ABORTED \u2014 {len(errors)} patch(es) failed:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

DST_ENGINE.write_text(src, encoding='utf-8')
print(f"\nengine_v85.py written ({len(src):,} bytes)")

# ── Syntax check ──────────────────────────────────────────────────────────────
import py_compile
try:
    py_compile.compile(str(DST_ENGINE), doraise=True)
    print("engine_v85.py: Python syntax OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# P12 — app.py: register engine_v85 + update default
# ══════════════════════════════════════════════════════════════════════════════
app = APP_PY.read_text(encoding='utf-8')

# Insert engine_v85 as first entry (most recent)
OLD_APP = '    "v8.45": BASE / "engine_v845.py",'
NEW_APP = '    "v8.5":  BASE / "engine_v85.py",\n    "v8.45": BASE / "engine_v845.py",'
if OLD_APP not in app:
    OLD_APP = '    "v8.4": BASE / "engine_v84.py",'
    NEW_APP = '    "v8.5":  BASE / "engine_v85.py",\n    "v8.4": BASE / "engine_v84.py",'
check(OLD_APP in app, "P12a ENGINE_SCRIPTS anchor")
app = app.replace(OLD_APP, NEW_APP, 1)

# Update cache check in _prewarm_ref_cache() to use v85 cache key
if 'ref_fp.v845.json' in app:
    app = app.replace('ref_fp.v845.json', 'ref_fp.v85.json', 1)
    print("OK:   P12b prewarm cache key → v85")

# Update engine lookup in _prewarm_ref_cache()
if '"v8.45"' in app and 'ENGINE_SCRIPTS.get("v8.45")' in app:
    app = app.replace(
        'ENGINE_SCRIPTS.get("v8.45") or ENGINE_SCRIPTS.get("v8.4")',
        'ENGINE_SCRIPTS.get("v8.5") or ENGINE_SCRIPTS.get("v8.45") or ENGINE_SCRIPTS.get("v8.4")',
        1
    )
    print("OK:   P12c prewarm engine lookup → v8.5")

# Update default engine
for old_def, new_def in [
    ('"engine": "v8.45",',           '"engine": "v8.5",'),
    ('"engine": "v8.4",',            '"engine": "v8.5",'),
    ('data.get("engine", "v8.45")',   'data.get("engine", "v8.5")'),
    ('data.get("engine", "v8.4")',    'data.get("engine", "v8.5")'),
]:
    if old_def in app:
        app = app.replace(old_def, new_def, 1)
        print(f"OK:   P12d default engine: {old_def.strip()[:40]} \u2192 v8.5")
        break

APP_PY.write_text(app, encoding='utf-8')
print("app.py updated")

if errors:
    print(f"\n{len(errors)} FAILED: {errors}")
    sys.exit(1)
else:
    print(f"\nAll patches applied.  Summary:")
    print(f"  engine_v85.py  {DST_ENGINE.stat().st_size:,} bytes")
    print(f"  app.py         {APP_PY.stat().st_size:,} bytes")
    print()
    print("What changed (v8.45 \u2192 v8.5):")
    print("  \u2022 _V85_MDS_WEIGHTS dict: 4 tiers with different SNR/HF emphasis")
    print("  \u2022 _compute_achievable_targets(): per-tier Crest/LRA/LUFS ceilings")
    print("  \u2022 compute_mds(): source_tier param, recomputed after tier detection")
    print("  \u2022 quality_score(): score_tier + score_absolute + ceiling_reason")
    print("  \u2022 64K_FLOOR ad-hoc hack: REMOVED")
    print("  \u2022 All 5 quality_score() calls: pass tier + cutoff")
    print("  \u2022 FINAL REPORT: shows both scores + ceiling reason")
    print("  \u2022 Return dict: score_absolute + score_tier + ceiling_reason exported")
    print()
    print("Deploy:")
    print("  cd ~/tilawa-enhancer")
    print("  git add engine_v85.py app.py")
    print("  git commit -m 'v8.5: tier-adjusted scoring "
          "\\u2014 honest ceiling for imperfect sources'")
    print("  git push https://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"
          "@github.com/c42742910-ops/tilawa-enhancer.git main")
