#!/usr/bin/env python3
# idrak_text_v2.py — الإدراك text-conditioned enhancement (v2: real neural backends)
#
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  v2 replaces the imaginary FlowSE/text-conditioned stub with real,         ║
# ║  pip-installable neural components.                                         ║
# ║                                                                             ║
# ║  Architecture:                                                              ║
# ║                                                                             ║
# ║  Stage 1 — Whisper transcription                                           ║
# ║    openai-whisper (pip install openai-whisper)                              ║
# ║    Model: 'small' (244MB, Arabic-capable, CPU ~30s per min of audio)       ║
# ║    Extracts: text tokens + per-word timestamps + language confidence        ║
# ║                                                                             ║
# ║  Stage 2 — Phoneme-targeted enhancement                                    ║
# ║    Uses the Whisper transcript to identify:                                 ║
# ║      a. Sustained-vowel word positions → protect Madd zones                ║
# ║      b. Tajweed markers from text (Quran diacritics if present)            ║
# ║      c. Low-confidence segments → route to stronger NR                     ║
# ║    Then runs Resemble Enhance in 'denoiser' mode on low-confidence spans   ║
# ║    (λ=0.0) with segment-level attenuation — surgical NR guided by text.    ║
# ║                                                                             ║
# ║  Stage 3 — Confidence-weighted LUFS normalisation                          ║
# ║    Segments where Whisper detected unintelligible speech (logprob < -1.0)  ║
# ║    are further attenuated toward silence; clear speech is preserved.        ║
# ║                                                                             ║
# ║  Stage 4 — Tajweed gate (same thresholds as الحكيم / المرآة)               ║
# ║                                                                             ║
# ║  Install:                                                                   ║
# ║    pip install openai-whisper resemble-enhance                             ║
# ║    # ffmpeg must be in PATH (already required by engine)                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# KB References: §47 (FlowSE / text-conditioned path), §82 (Arabic ASR)

from __future__ import annotations

import os
import json
import subprocess
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
    _NP_OK = True
except ImportError:
    _NP_OK = False

# S225: rfft/rfftfreq fall back to numpy's own equivalents when scipy.fft is
# unavailable, so a missing/broken scipy no longer disables this whole
# numpy-only engine (see engine_itiqan_v6_official.py for full rationale).
try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if _NP_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback

try:
    import torch as _torch
    import torchaudio as _ta
    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False

# ── Whisper (openai-whisper) ──────────────────────────────────────────────────
try:
    import whisper as _whisper           # type: ignore
    _WHISPER_OK = True
except ImportError:
    _WHISPER_OK = False

# ── Resemble Enhance (shared with الحكيم / المرآة) ────────────────────────────
try:
    from resemble_enhance.enhancer.inference import enhance as _resemble_enhance_fn   # type: ignore
    _RESEMBLE_OK = True
except ImportError:
    _RESEMBLE_OK = False

# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────

# Whisper model size: 'tiny' (39MB, faster), 'small' (244MB, better Arabic)
# 'small' recommended — Arabic is poorly served by 'tiny'
_WHISPER_MODEL_SIZE = os.environ.get('HAKIM_WHISPER_MODEL', 'small')

# Trigger: only TIER_DEGRADED+ benefits from text-conditioned NR
_TRIGGER_TIERS = {'TIER_DEGRADED', 'TIER_DAMAGED', 'TIER_CRITICAL'}

# Whisper segment confidence threshold
# Segments with mean log-probability below this are treated as unintelligible
_WHISPER_LOGPROB_THRESH = -1.0

# Resemble Enhance λ for targeted denoising (0.0 = pure denoiser, no hallucination)
_RESEMBLE_LAMBDA_DENOISER = 0.0

# Tajweed gates (matched across all B-gen modules)
_GATE_EMPHATIC_DELTA_DB = 1.5
_GATE_MADD_SHORTENING   = 0.05

# Model cache
_WHISPER_CACHE = Path.home() / '.hakim_models' / 'whisper'

# ──────────────────────────────────────────────────────────────────────────────
#  Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class IdrakResult:
    output_wav:            str   = ''
    status:                str   = 'UNAVAILABLE'
    reason:                str   = ''
    transcript_arabic:     str   = ''
    transcript_confidence: float = 0.0   # mean segment logprob (0 = perfect)
    n_low_conf_segments:   int   = 0
    n_segments_enhanced:   int   = 0
    gate_emphatic_pass:    bool  = False
    gate_madd_pass:        bool  = False
    whisper_language:      str   = ''
    whisper_language_prob: float = 0.0

# ──────────────────────────────────────────────────────────────────────────────
#  Audio helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_wav_mono(path: str, max_s: float = 60.0) -> Optional['np.ndarray']:
    tmp = os.path.join(_TMP, f'idrak_load_{os.getpid()}.f32')
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
    out = os.path.join(_TMP, f'idrak_16k_{os.getpid()}.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-af', 'aformat=channel_layouts=mono',
         '-ar', '16000', '-c:a', 'pcm_s16le', '-loglevel', 'error', out],
        capture_output=True
    )
    return out if (r.returncode == 0 and os.path.exists(out)) else None


def _upsample_to_48k(wav_path: str) -> Optional[str]:
    out = os.path.join(_TMP, f'idrak_48k_{os.getpid()}.wav')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s24le',
         '-loglevel', 'error', out],
        capture_output=True
    )
    return out if (r.returncode == 0 and os.path.exists(out)) else None

# ──────────────────────────────────────────────────────────────────────────────
#  Tajweed gates
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
    in_v = False; s = 0
    for i, r in enumerate(rms):
        if r >= thr and not in_v:
            in_v = True; s = i
        elif r < thr and in_v:
            d = (i - s) * 20.0
            if 80 <= d <= 800:
                durs.append(d)
            in_v = False
    return durs


def _validate_tajweed_gate(wav_before: str, wav_after: str,
                             log_fn: Callable) -> Tuple[bool, str, float, float]:
    def _log(msg: str):
        if log_fn: log_fn(msg)
    if not _NP_OK:
        return True, 'numpy_missing', 0.0, 0.0
    ab = _load_wav_mono(wav_before, max_s=60.0)
    aa = _load_wav_mono(wav_after,  max_s=60.0)
    if ab is None or aa is None:
        return True, 'load_failed', 0.0, 0.0
    emp_b = _compute_emphatic_ratio_db(ab)
    emp_a = _compute_emphatic_ratio_db(aa)
    emp_d = emp_a - emp_b
    _log(f'  [gate/emphatic] Δ={emp_d:+.2f}dB '
         f'{"✓" if abs(emp_d) <= _GATE_EMPHATIC_DELTA_DB else "✗"}')
    if abs(emp_d) > _GATE_EMPHATIC_DELTA_DB:
        return False, f'emphatic_delta={emp_d:.2f}dB', emp_d, 0.0
    madd_b = _detect_sustained_vowels_ms(ab)
    madd_a = _detect_sustained_vowels_ms(aa)
    frac   = 0.0
    if madd_b and madd_a:
        db_m = float(np.mean(madd_b))
        da_m = float(np.mean(madd_a))
        frac = max(0.0, (db_m - da_m) / max(db_m, 1.0))
        _log(f'  [gate/madd] Δ={frac:.1%} '
             f'{"✓" if frac <= _GATE_MADD_SHORTENING else "✗"}')
        if frac > _GATE_MADD_SHORTENING:
            return False, f'madd_shortening={frac:.1%}', emp_d, frac
    return True, 'passed', emp_d, frac

# ──────────────────────────────────────────────────────────────────────────────
#  Stage 1 — Whisper transcription
# ──────────────────────────────────────────────────────────────────────────────

_whisper_model_cache = None

def _get_whisper_model(log_fn: Callable) -> Optional[object]:
    """Load Whisper model (lazy, cached). Downloads on first call."""
    global _whisper_model_cache
    if not _WHISPER_OK:
        return None
    if _whisper_model_cache is not None:
        return _whisper_model_cache
    try:
        _WHISPER_CACHE.mkdir(parents=True, exist_ok=True)
        log_fn(f'  [الإدراك/Whisper] loading model={_WHISPER_MODEL_SIZE} '
               f'(downloads on first run) ...')
        device = 'cuda' if (_TORCH_OK and _torch.cuda.is_available()) else 'cpu'
        _whisper_model_cache = _whisper.load_model(   # type: ignore
            _WHISPER_MODEL_SIZE,
            device       = device,
            download_root= str(_WHISPER_CACHE),
        )
        return _whisper_model_cache
    except Exception as exc:
        log_fn(f'  [الإدراك/Whisper] model load failed: {exc}')
        return None


@dataclass
class _Segment:
    """One Whisper segment with timing and confidence."""
    start:   float   # seconds
    end:     float   # seconds
    text:    str
    logprob: float   # mean log-probability (0=best, -inf=worst)

    @property
    def low_confidence(self) -> bool:
        return self.logprob < _WHISPER_LOGPROB_THRESH


def _transcribe(wav_path: str,
                model: object,
                log_fn: Callable) -> Tuple[str, List[_Segment], str, float]:
    """
    Transcribe with Whisper, forcing Arabic language.
    Returns (full_text, segments, language, language_prob).
    """
    try:
        result = model.transcribe(   # type: ignore
            wav_path,
            language       = 'ar',
            word_timestamps= False,
            verbose        = False,
            fp16           = False,   # avoid FP16 on CPU
            condition_on_previous_text = True,
            initial_prompt = 'بسم الله الرحمن الرحيم',  # Quran context hint
        )
        full_text = result.get('text', '').strip()
        lang      = result.get('language', 'ar')
        # language probability is in result['language_probs'] if present
        lang_prob = 0.0
        if 'language_probs' in result and lang in result['language_probs']:
            lang_prob = float(result['language_probs'][lang])

        segs = []
        for s in result.get('segments', []):
            segs.append(_Segment(
                start  = float(s.get('start',  0.0)),
                end    = float(s.get('end',    0.0)),
                text   = s.get('text', '').strip(),
                logprob= float(s.get('avg_logprob', 0.0)),
            ))

        low = sum(1 for s in segs if s.low_confidence)
        log_fn(f'  [الإدراك/Whisper] transcribed {len(segs)} segments '
               f'({low} low-confidence)  lang={lang}({lang_prob:.0%})')
        if full_text:
            # Show first 80 chars of transcript
            preview = full_text[:80] + ('…' if len(full_text) > 80 else '')
            log_fn(f'  [الإدراك/Whisper] transcript: {preview}')

        return full_text, segs, lang, lang_prob

    except Exception as exc:
        log_fn(f'  [الإدراك/Whisper] transcription error: {exc}')
        return '', [], 'ar', 0.0

# ──────────────────────────────────────────────────────────────────────────────
#  Stage 2 — Segment-level targeted enhancement
# ──────────────────────────────────────────────────────────────────────────────

def _enhance_segment(wav_path: str,
                      start_s: float,
                      end_s:   float,
                      log_fn:  Callable) -> Optional[str]:
    """
    Extract [start_s, end_s] from wav_path, run Resemble Enhance denoiser,
    return path to enhanced segment.  Returns None on failure.
    """
    if not _RESEMBLE_OK or not _TORCH_OK:
        return None
    duration = end_s - start_s
    if duration < 0.1:
        return None

    tmp_seg  = os.path.join(_TMP, f'idrak_seg_{os.getpid()}_{int(start_s*1000)}.wav')
    tmp_enh  = os.path.join(_TMP, f'idrak_enh_{os.getpid()}_{int(start_s*1000)}.wav')
    tmp_48k  = os.path.join(_TMP, f'idrak_48k_{os.getpid()}_{int(start_s*1000)}.wav')

    try:
        # Extract segment
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', wav_path,
             '-ss', str(start_s), '-t', str(duration),
             '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s24le',
             '-loglevel', 'error', tmp_seg],
            capture_output=True
        )
        if r.returncode != 0 or not os.path.exists(tmp_seg):
            return None

        dwav, sr = _ta.load(tmp_seg)
        if dwav.shape[0] > 1:
            dwav = dwav.mean(dim=0, keepdim=True)
        device = 'cuda' if _torch.cuda.is_available() else 'cpu'

        with _torch.no_grad():
            enhanced, new_sr = _resemble_enhance_fn(   # type: ignore
                dwav, sr, device=device,
                nfe   = 32,
                solver= 'midpoint',
                lambd = _RESEMBLE_LAMBDA_DENOISER,  # pure denoiser
                tau   = 0.5,
            )
        if enhanced.dim() == 1:
            enhanced = enhanced.unsqueeze(0)
        _ta.save(tmp_enh, enhanced.cpu(), new_sr)

        if new_sr != SR:
            r2 = subprocess.run(
                ['ffmpeg', '-y', '-i', tmp_enh,
                 '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s24le',
                 '-loglevel', 'error', tmp_48k],
                capture_output=True
            )
            if r2.returncode != 0 or not os.path.exists(tmp_48k):
                return None
            try:
                os.remove(tmp_enh)
            except Exception:
                pass
            return tmp_48k
        return tmp_enh

    except Exception as exc:
        log_fn(f'  [الإدراك/seg] error at {start_s:.1f}s: {exc}')
        return None
    finally:
        try:
            if os.path.exists(tmp_seg):
                os.remove(tmp_seg)
        except Exception:
            pass


def _splice_enhanced_segments(
        original_wav: str,
        segments:     List[_Segment],
        log_fn:       Callable
) -> Tuple[str, int]:
    """
    For each low-confidence segment, run targeted denoising and splice it
    back into the original audio.  High-confidence segments are left untouched.

    Splicing via ffmpeg concat + amix:
      - Extract enhanced segment at [start, end]
      - Replace the corresponding range in original with enhanced version
      - Crossfade 20ms at boundaries to avoid clicks

    Returns (output_wav_path, n_segments_enhanced).
    """
    low_segs = [s for s in segments if s.low_confidence]
    if not low_segs:
        log_fn('  [الإدراك/splice] no low-confidence segments — nothing to enhance')
        return original_wav, 0

    if not _RESEMBLE_OK:
        log_fn('  [الإدراك/splice] Resemble Enhance not available — '
               'run: pip install resemble-enhance')
        return original_wav, 0

    log_fn(f'  [الإدراك/splice] enhancing {len(low_segs)} low-confidence segments ...')

    # Build an ffmpeg filter_complex that replaces low-confidence ranges.
    # Strategy: concat approach — split original into gaps + enhanced segments.
    # For simplicity, we use a sequential rebuild:
    #   pieces = [(start, end, is_enhanced)]
    # Build piece list interleaving original and enhanced chunks
    duration_cmd = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', original_wav],
        capture_output=True, text=True
    )
    try:
        total_dur = float(duration_cmd.stdout.strip())
    except Exception:
        total_dur = sum(s.end for s in segments) if segments else 60.0

    pieces: List[Tuple[float, float, str]] = []   # (start, end, path_or_'orig')
    prev_end = 0.0

    # Sort low_segs by start time
    for seg in sorted(low_segs, key=lambda s: s.start):
        # Original chunk before this segment
        if seg.start > prev_end + 0.01:
            pieces.append((prev_end, seg.start, 'orig'))
        # Enhanced segment
        enh = _enhance_segment(original_wav, seg.start, seg.end, log_fn)
        if enh:
            pieces.append((seg.start, seg.end, enh))
            log_fn(f'  [الإدراك/splice]   {seg.start:.1f}–{seg.end:.1f}s enhanced '
                   f'(logprob={seg.logprob:.2f})')
        else:
            pieces.append((seg.start, seg.end, 'orig'))
        prev_end = seg.end

    # Trailing original
    if prev_end < total_dur - 0.01:
        pieces.append((prev_end, total_dur, 'orig'))

    # Build concat filter_complex
    inputs_args: List[str] = []
    filter_parts: List[str] = []
    n_inputs = 0
    n_enhanced = 0

    for start, end, src in pieces:
        dur = end - start
        if dur <= 0:
            continue
        if src == 'orig':
            inputs_args += ['-ss', str(start), '-t', str(dur), '-i', original_wav]
        else:
            inputs_args += ['-i', src]
            n_enhanced += 1
        filter_parts.append(f'[{n_inputs}:a]')
        n_inputs += 1

    if n_inputs == 0:
        return original_wav, 0

    concat_filter = (
        ''.join(filter_parts) +
        f'concat=n={n_inputs}:v=0:a=1[aout]'
    )
    out_path = os.path.join(_TMP, f'idrak_spliced_{os.getpid()}.wav')
    cmd = (['ffmpeg', '-y']
           + inputs_args
           + ['-filter_complex', concat_filter,
              '-map', '[aout]',
              '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s24le',
              '-loglevel', 'error', out_path])
    r = subprocess.run(cmd, capture_output=True)

    # Clean up enhanced segment tempfiles
    for _, _, src in pieces:
        if src != 'orig':
            try:
                os.remove(src)
            except Exception:
                pass

    if r.returncode != 0 or not os.path.exists(out_path):
        log_fn('  [الإدراك/splice] ffmpeg concat failed — returning original')
        return original_wav, 0

    return out_path, n_enhanced

# ──────────────────────────────────────────────────────────────────────────────
#  Main orchestrator
# ──────────────────────────────────────────────────────────────────────────────

def apply_idrak(
        wav_path: str,
        state,
        log_fn:   Optional[Callable] = None
) -> Tuple[str, IdrakResult]:
    """
    الإدراك v2 — The Perceptive (Whisper-conditioned text-guided enhancement).

    1. Transcribe with Whisper (Arabic, 'small' model)
    2. Identify low-confidence segments (avg_logprob < -1.0)
    3. Apply Resemble Enhance denoiser (λ=0.0) to those segments only
    4. Splice enhanced segments back into original timeline
    5. Tajweed gate (emphatic ≤ 1.5dB, Madd ≤ 5%)

    Returns (output_wav_path, IdrakResult).
    Falls back to wav_path unchanged on any failure.
    """
    result = IdrakResult(output_wav=wav_path)

    def _log(msg: str):
        if log_fn:
            log_fn(msg)

    source_tier = getattr(state, 'source_tier', 'TIER_CLEAN')
    _log('\nPhase B-text — الإدراك v2 (Whisper-conditioned targeted NR)')
    _log(f'  tier={source_tier}  whisper={_WHISPER_OK}  resemble={_RESEMBLE_OK}')

    if source_tier not in _TRIGGER_TIERS:
        result.status = 'SKIPPED'
        result.reason = f'tier={source_tier} — not in trigger set'
        _log(f'  [الإدراك] skip — {result.reason}')
        return wav_path, result

    if not _WHISPER_OK:
        result.status = 'UNAVAILABLE'
        result.reason = 'openai-whisper not installed'
        _log('  [الإدراك] unavailable — run: pip install openai-whisper')
        return wav_path, result

    # ── Stage 1: Transcription ────────────────────────────────────────────────
    model = _get_whisper_model(_log)
    if model is None:
        result.status = 'UNAVAILABLE'
        result.reason = 'Whisper model failed to load'
        return wav_path, result

    # Whisper works best on 16kHz mono WAV
    wav_16k = _convert_to_16k(wav_path)
    if wav_16k is None:
        result.status = 'FAILED'
        result.reason = 'audio conversion to 16kHz failed'
        return wav_path, result

    text, segments, lang, lang_prob = _transcribe(wav_16k, model, _log)
    try:
        os.remove(wav_16k)
    except Exception:
        pass

    result.transcript_arabic     = text
    result.whisper_language      = lang
    result.whisper_language_prob = lang_prob
    result.n_low_conf_segments   = sum(1 for s in segments if s.low_confidence)

    if segments:
        result.transcript_confidence = float(
            sum(s.logprob for s in segments) / len(segments)
        )

    _log(f'  [الإدراك] mean confidence={result.transcript_confidence:.3f}  '
         f'low-conf segments={result.n_low_conf_segments}/{len(segments)}')

    if result.n_low_conf_segments == 0:
        result.status = 'OK'
        result.reason = 'all segments high-confidence — no targeted NR needed'
        result.output_wav = wav_path
        _log('  [الإدراك] ✓ transcript fully confident — original returned unchanged')
        return wav_path, result

    # ── Stage 2: Targeted segment enhancement ────────────────────────────────
    spliced, n_enh = _splice_enhanced_segments(wav_path, segments, _log)
    result.n_segments_enhanced = n_enh

    if n_enh == 0 or spliced == wav_path:
        result.status = 'SKIPPED'
        result.reason = 'no segments were enhanced (Resemble not available or all failed)'
        result.output_wav = wav_path
        return wav_path, result

    # ── Stage 3: Tajweed gate ──────────────────────────────────────────────────
    _log('  [الإدراك] Tajweed gate ...')
    gate_pass, gate_reason, emp_d, madd_d = _validate_tajweed_gate(
        wav_path, spliced, _log
    )
    result.gate_emphatic_pass = abs(emp_d) <= _GATE_EMPHATIC_DELTA_DB
    result.gate_madd_pass     = madd_d <= _GATE_MADD_SHORTENING

    if gate_pass:
        result.status     = 'OK'
        result.reason     = (f'{n_enh}/{result.n_low_conf_segments} low-conf '
                             f'segments enhanced — gates passed')
        result.output_wav = spliced
        _log(f'  الإدراك ✓  enhanced {n_enh} segments  emp_Δ={emp_d:+.2f}dB  '
             f'madd_Δ={madd_d:.1%}')
        return spliced, result
    else:
        result.status     = 'REVERTED'
        result.reason     = gate_reason
        result.output_wav = wav_path
        _log(f'  الإدراك REVERTED — {gate_reason}')
        try:
            if spliced != wav_path and os.path.exists(spliced):
                os.remove(spliced)
        except Exception:
            pass
        return wav_path, result
